import json
import ssl
import threading
import time
from urllib.parse import urlparse

from zeep.wsse.utils import get_unique_id

from odoo import models, fields, api, SUPERUSER_ID

import sys
import os
import logging

from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

# Force Python to load the local 'pika' library
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, '..', 'lib')
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

try:
    import pika
except ModuleNotFoundError as e:
    _logger.error("Failed to load bundled Pika library: %s", e)
    raise

def get_client_base_url():
    if request:
        # Get the full URL from the HTTP request
        full_url = request.httprequest.url
        # Parse the URL to extract the scheme and netloc (base URL)
        parsed_url = urlparse(full_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        return base_url
    return None

def _parse_progress_message(message):
    """ Extract task status dictionary from json from the message """
    try:
        status = json.loads(message)
        return status
    except Exception as e:
        _logger.error("Error parsing progress message: %s", e)
        return None, None

def _get_rmq_parameters(params):
    _host = 'amqp.maylasoftware.com'
    _user = 'admin'
    _password = '123'
    context = ssl.create_default_context()
    credentials = pika.PlainCredentials(_user, _password)
    parameters = pika.ConnectionParameters(
        host=_host,
        port=5672,
        credentials=credentials,
        ssl_options=pika.SSLOptions(context)
    )
    return parameters


running_listener = False

def set_running_listener(running: bool):
    global running_listener
    running_listener = running

def get_running_listener() -> bool:
    global running_listener
    return running_listener

def start_listen_rabbitmq(env):
    """ Listen for progress updates from RabbitMQ """
    try:
        if get_running_listener():
            _logger.warning("Already listening for progress updates.")
            return

        if not env:
            _logger.error("Failed to get environment")
            return

        params = env['ir.config_parameter'].sudo()

        connection = pika.BlockingConnection(_get_rmq_parameters(params))
        channel = connection.channel()

        set_running_listener(True)

        # Declare the progress queue
        channel.queue_declare(queue='task_progress_queue', durable=True)

        def callback(ch, method, properties, body):
            # Update progress in Odoo
            task = False

            try:
                cr = env.registry.cursor()
                _env = api.Environment(cr, SUPERUSER_ID, {})

                message = body.decode()

                # Parse the task name and progress percentage
                status = _parse_progress_message(message)
                task_name = status.get('Name')
                task_model = status.get('Model')
                progress = status.get('Progress')
                task_done = status.get('Done')
                task_cancelled = status.get('Cancelled')
                task_errors = status.get('Errors')
                task_message = status.get('Message')

                task_model = _env[task_model]

                # Search for the task by name
                task = task_model.search([('name', '=', task_name)], limit=1)
                if task:
                    task = task.sudo().with_context({'for_update': True})
                    if task_done:
                        task.write({'state': 'done', 'result': 'Task completed successfully.'})
                        _logger.info("Task '%s' completed successfully.", task_name)
                    elif task_cancelled:
                        task.write({'state': 'draft', 'result': 'Task cancelled.', 'message': ''})
                        _logger.info("Task '%s' cancelled.", task_name)

                    if progress and progress >= 0:
                        task.write({'progress': progress})

                    _logger.info("Progress updated for task '%s' to %s%%", task_name, progress)

                    if task_errors:
                        task.write({'state': 'draft', 'result': 'Task failed: ' + task_errors})
                        _logger.error("Task '%s' failed: %s", task_name, task_errors)

                    if task_message:
                        task.write({'message': task_message})
                        _logger.info("Task '%s' message: %s", task_name, task_message)
                else:
                    _logger.warning("Task '%s' not found.", task_name)

                if task_message:
                    _logger.info("Task message: %s", task_message)
            except Exception as e:
                _logger.error("Error processing progress message: %s", e)
            finally:
                _env['bus.bus']._sendone('refresh_progress_bar', 'reload_data', {
                    'type': 'success',
                    'message': 'Task progress updated.'
                })

                _env.cr.commit()
                _env.cr.close()

        # Start consuming progress updates
        channel.basic_consume(queue='task_progress_queue', on_message_callback=callback, auto_ack=True)
        _logger.info("Listening for progress updates...")
        channel.start_consuming()

    except Exception as e:
        _logger.error("Error listening for progress updates: %s", e)
    finally:
        set_running_listener(False)


class DataTask(models.Model):
    _name = 'data.task'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Data Task'

    name = fields.Char(string='Name', required=True)
    progress = fields.Float(string='Progress')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], string='State', default='draft')

    result = fields.Text(string='Result')
    message = fields.Text(string='Message')

    operation = fields.Selection([
        ('import_orders', 'Import Orders'),
        ('export_invoices', 'Export Invoices'),
        ('export_stock_moves', 'Export Stock Moves')
    ], string='Operation', default='import_orders')

    def default_get(self, fields_list):
        res = super(DataTask, self).default_get(fields_list)
        res['name'] = get_unique_id()
        return res

    def action_start(self):
        """ Publish a task request to RabbitMQ """
        self.ensure_one()
        self.write({'state': 'in_progress', 'result': '', 'message': '', 'progress': 0.0})
        try:
            self._send_request_queue_message(self.operation)
            _logger.info("Task request sent: %s", self.name)
        except UserError as e:
            raise e
        except Exception as e:
            _logger.error("Error sending task request: %s", e)

    def _send_request_queue_message(self, operation):
        params = self.env['ir.config_parameter'].sudo()
        _license = params.get_param('comarch_exchange.comarch_service_licanse_key')
        if not _license:
            self.write({'state': 'draft', 'result': 'Task failed.',
                        'message': 'Comarch Service License Key is not set. Open settings and set the license key from "Comarch EDI" tab.'})
            self.env.cr.commit()
            raise UserError(
                'Comarch Service License Key is not set. Open settings and set the license key from "Comarch EDI" tab.')

        if not get_running_listener():
            threading.Thread(target=start_listen_rabbitmq, args=(self.env,)).start()
            _index = 0
            while not get_running_listener():
                time.sleep(0.2)
                _index += 1
                if _index > 10:
                    break

            if not get_running_listener():
                threading.Thread(target=start_listen_rabbitmq, args=(self.env,)).start()
                return

        parameters = _get_rmq_parameters(params)

        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        # Declare the task request queue
        channel.queue_declare(queue='task_request_queue', durable=True)
        odoo_address = get_client_base_url()
        odoo_database = self.env.cr.dbname
        connection_data = {
            'address': odoo_address,
            'database': odoo_database
        }

        # Send the task name as a message
        message_object = {'name': self.name,
                          'model': self._name,
                          'license': _license,
                          'operation': operation,
                          'connection': connection_data}
        message = str(message_object)
        channel.basic_publish(exchange='', routing_key='task_request_queue', body=message.encode())

    def action_stop(self):
        self.ensure_one()
        try:
            self._send_request_queue_message('cancel')
        except Exception as e:
            _logger.error("Error sending task cancel request: %s", e)

    def unlink(self):
        for task in self:
            if task.state == 'in_progress':
                task.action_stop()
        return super(DataTask, self).unlink()

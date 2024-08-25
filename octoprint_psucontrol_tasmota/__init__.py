# coding=utf-8
from __future__ import absolute_import

__author__ = "Shawn Bruce <kantlivelong@gmail.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2021 Shawn Bruce - Released under terms of the AGPLv3 License"

import octoprint.plugin
import requests

class PSUControl_Tasmota(octoprint.plugin.StartupPlugin,
                         octoprint.plugin.RestartNeedingPlugin,
                         octoprint.plugin.TemplatePlugin,
                         octoprint.plugin.SettingsPlugin):

    def __init__(self):
        self.config = dict()


    def get_settings_defaults(self):
        return dict(
            address = '',
            plug = 1,
            enable_auth = False,
            username = 'admin',
            password = ''
        )


    def on_settings_initialized(self):
        self.reload_settings()


    def reload_settings(self):
        for k, v in self.get_settings_defaults().items():
            if type(v) == str:
                v = self._settings.get([k])
            elif type(v) == int:
                v = self._settings.get_int([k])
            elif type(v) == float:
                v = self._settings.get_float([k])
            elif type(v) == bool:
                v = self._settings.get_boolean([k])

            self.config[k] = v
            self._logger.debug("{}: {}".format(k, v))


    def on_startup(self, host, port):
        psucontrol_helpers = self._plugin_manager.get_helpers("psucontrol")
        if not psucontrol_helpers or 'register_plugin' not in psucontrol_helpers.keys():
            self._logger.warning("The version of PSUControl that is installed does not support plugin registration.")
            return

        self._logger.debug("Registering plugin with PSUControl")
        psucontrol_helpers['register_plugin'](self)


    def send(self, cmd):
        url = "http://{}/cm".format(self.config['address'])

        params = dict(cmnd=cmd, timeout=5)

        if self.config['enable_auth']:
            params['user'] = self.config['username']
            params['password'] = self.config['password']

        response = None
        try:
            response = requests.get(url, params=params)
        except (
                requests.exceptions.InvalidURL,
                requests.exceptions.ConnectionError
        ):
            self._logger.error("Unable to communicate with device. Check settings.")
        except Exception:
            self._logger.exception("Exception while making API call")
        else:
            self._logger.debug("cmd={}, status_code={}, text={}".format(cmd, response.status_code, response.text))

            if response.status_code == 401:
                self._logger.warning("Server returned 401 Unauthorized. Check credentials.")
                response = None

        return response


    def change_psu_state(self, state):
        cmd = "Power{} {}".format(self.config['plug'], state)
        self.send(cmd)


    def turn_psu_on(self):
        self._logger.debug("Switching PSU On")
        self.change_psu_state('on')


    def turn_psu_off(self):
        self._logger.debug("Switching PSU Off")
        self.change_psu_state('off')


    def get_psu_state(self):
        # First try the "Power"-cmd
        cmd = "Power{}".format(self.config['plug'])

        response = self.send(cmd)
        if not response:
            return False
        data = response.json()

        status = None
        try:
            # On some devices it seems to add the plug number, on others it doesn't.
            # So check for both variants.
            status = ((data.get('POWER' + str(self.config['plug'])) or data.get('POWER')) == 'ON')
        except KeyError:
            pass

        if status != None:
            return status

        # If that didn't work, try the "Status"-cmd
        cmd = "Status 0"

        response = self.send(cmd)
        if not response:
            return False
        data = response.json()

        status = None
        try:
            status = (data['StatusSTS']['POWER' + str(self.config['plug'])] == 'ON')
        except KeyError:
            pass

        if status == None and self.config['plug'] == 1:
            try:
                status = (data['StatusSTS']['POWER'] == 'ON')
            except KeyError:
                pass

        if status == None:
            self._logger.error("Unable to determine status. Check settings.")
            status = False

        return status


    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self.reload_settings()


    def get_settings_version(self):
        return 1


    def on_settings_migrate(self, target, current=None):
        pass


    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]


    def get_update_information(self):
        return dict(
            psucontrol_tasmota=dict(
                displayName="PSU Control - Tasmota",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="kantlivelong",
                repo="OctoPrint-PSUControl-Tasmota",
                current=self._plugin_version,

                # update method: pip w/ dependency links
                pip="https://github.com/kantlivelong/OctoPrint-PSUControl-Tasmota/archive/{target_version}.zip"
            )
        )

__plugin_name__ = "PSU Control - Tasmota"
__plugin_pythoncompat__ = ">=2.7,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PSUControl_Tasmota()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }

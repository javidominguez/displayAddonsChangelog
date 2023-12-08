#!/usr/bin/python
#-coding: UTF-8 -*-

"""
Display addons change log

Proposal for #14041

This file is covered by the GNU General Public License.
See the file COPYING.txt for more details.
Copyright (C) 2023 Javi Dominguez <fjavids@gmail.com>
"""

from logHandler import log
import addonHandler
from addonHandler import Addon, getAvailableAddons, _availableAddons, state, AddonStateCategory
import globalPluginHandler
import gui
import os

# addonHandler.installAddonBundle function modified to resolve #14041
def installAddonBundle(bundle: "AddonBundle") -> "Addon":
	""" Extracts an Addon bundle in to a unique subdirectory of the user addons directory,
	marking the addon as needing 'install completion' on NVDA restart.
	"""
	bundle.extract()
	addon = Addon(bundle.pendingInstallPath)
	# #2715: The add-on must be added to _availableAddons here so that
	# translations can be used in installTasks module.
	_availableAddons[addon.path]=addon
	# start of modifications for #14041
	try:
		installedAddon = next(getAvailableAddons(filterFunc=lambda a: a.name == addon.name))
	except StopIteration:
		# An addon with the same name as the one being installed is not installed.
		pass
	else:
		if addon.version !=installedAddon.version:
			# There is a different version of the addon being installed, therefore, since it is an update, the changelog is displayed.
			# It would be better to check that the new version is greater than the installed one but perhaps the version numbering formats are too variable to do this reliably.
			displayAddonChangelog(addon)
	# End of modifications
	try:
		addon.runInstallTask("onInstall")
	except:
		log.error("task 'onInstall' on addon '%s' failed"%addon.name,exc_info=True)
		del _availableAddons[addon.path]
		addon.completeRemove(runUninstallTask=False)
		raise AddonError("Installation failed")
	state[AddonStateCategory.PENDING_INSTALL].add(bundle.manifest['name'])
	state.save()
	return addon

# Function to add to addonHandler
def displayAddonChangelog(addon, changelogFileName="changelog.txt"):
	path = os.path.join(
		os.path.split(
		addon.getDocFilePath())[0],
		changelogFileName)
	if not os.path.exists(path): return False
	title = _("Whats new in {addonSummary} {addonVersion}").format(
		addonSummary = addon.manifest["summary"],
		addonVersion = addon.version
	)
	with open(path, "r", encoding="utf-8") as f:
		body = f.read()
	gui.messageBox(body, title)
	return True


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self, *args, **kwargs):
		super(GlobalPlugin, self).__init__(*args, **kwargs)
		setattr(addonHandler, "displayAddonChangelog", displayAddonChangelog)
		setattr(addonHandler, "installAddonBundle", installAddonBundle)

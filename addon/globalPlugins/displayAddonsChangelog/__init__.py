#!/usr/bin/python
#-coding: UTF-8 -*-

"""
Display addons change log

Proposal for #14041

This file is covered by the GNU General Public License.
See the file COPYING.txt for more details.
Copyright (C) 2023 Javi Dominguez <fjavids@gmail.com>
"""

import addonHandler
from addonHandler import Addon
import globalPluginHandler
from logHandler import log
import os
import systemUtils
import gui
import wx
import winKernel
import zipfile

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self, *args, **kwargs):
		super(GlobalPlugin, self).__init__(*args, **kwargs)
		setattr(gui.addonGui, "installAddon", installAddon)

# #14041 gui.addonGui.installAddon function to display a changelog in the ialog asking if the user wishes to update a previously installed addon.
def installAddon(parentWindow: wx.Window, addonPath: str) -> bool:  # noqa: C901
	"""Installs the addon bundle at path.
	Only used for installing external add-on bundles.
	Any error messages / warnings are presented to the user via a GUI message box.
	If attempting to install an addon that is pending removal, it will no longer be pending removal.
	@return True on success or False on failure.
	@note See also L{addonStore.install.installAddon}
	"""
	from gui.addonStoreGui.controls.messageDialogs import (
		_showAddonRequiresNVDAUpdateDialog,
		_showConfirmAddonInstallDialog,
		_shouldInstallWhenAddonTooOldDialog,
	)

	try:
		bundle = addonHandler.AddonBundle(addonPath)
	except:  # noqa: E722
		log.error("Error opening addon bundle from %s" % addonPath, exc_info=True)
		gui.messageBox(
			# Translators: The message displayed when an error occurs when opening an add-on package for adding.
			_("Failed to open add-on package file at %s - missing file or invalid file format") % addonPath,
			# Translators: The title of a dialog presented when an error occurs.
			_("Error"),
			wx.OK | wx.ICON_ERROR,
		)
		return False  # Exit early, can't install an invalid bundle

	if not bundle._hasGotRequiredSupport:
		_showAddonRequiresNVDAUpdateDialog(parentWindow, bundle._addonGuiModel)
		return False  # Exit early, addon does not have required support
	elif bundle.canOverrideCompatibility:
		shouldInstall, rememberChoice = _shouldInstallWhenAddonTooOldDialog(
			parentWindow,
			bundle._addonGuiModel,
		)
		if shouldInstall:
			# Install incompatible version
			bundle.enableCompatibilityOverride()
		else:
			# Exit early, addon is not up to date with the latest API version.
			return False
	elif wx.YES != _showConfirmAddonInstallDialog(parentWindow, bundle._addonGuiModel):
		return False  # Exit early, User changed their mind about installation.

	from addonStore.install import _getPreviouslyInstalledAddonById

	prevAddon = _getPreviouslyInstalledAddonById(bundle)
	if prevAddon:
		summary = bundle.manifest["summary"]
		curVersion = prevAddon.manifest["version"]
		newVersion = bundle.manifest["version"]

		# Translators: A title for the dialog asking if the user wishes to update a previously installed
		# add-on with this one.
		messageBoxTitle = _("Add-on Installation")

		overwriteExistingAddonInstallationMessage = _(
			# Translators: A message asking if the user wishes to update an add-on with the same version
			# currently installed according to the version number.
			"You are about to install version {newVersion} of {summary},"
			" which appears to be already installed. "
			"Would you still like to update?",
		).format(summary=summary, newVersion=newVersion)

		updateAddonInstallationMessage = _(
			# Translators: A message asking if the user wishes to update a previously installed
			# add-on with this one.
			"A version of this add-on is already installed. "
			"Would you like to update {summary} version {curVersion} to version {newVersion}?",
		).format(summary=summary, curVersion=curVersion, newVersion=newVersion)

# Start of modifications for #14041:
		# Extract only the manifest and changelog files from the bundle.
		with zipfile.ZipFile(bundle._path, 'r') as z:
			for info in z.infolist():
				if isinstance(info.filename, bytes):
					# #2505: Handle non-Unicode file names.
					info.filename = info.filename.decode("cp%d" % winKernel.kernel32.GetOEMCP())
				filename = os.path.split(info.filename.lower())[1]
				if filename == "changelog.txt" or filename == "manifest.ini":
					z.extract(info, bundle.pendingInstallPath)
		# If the documentation includes a changelog.txt file:
		docAddon = Addon(bundle.pendingInstallPath)
		changelogPath = docAddon.getDocFilePath(fileName="changelog.txt")
		if changelogPath:
			with open(changelogPath, "r", encoding="utf-8") as f:
				changelogText = f.read()
			# Add the contents of the changelog.txt file to the confirmation dialog message.
			updateAddonInstallationMessage = "\n".join((
				updateAddonInstallationMessage,
				#Translators: Displayed in the update addon installation message when a changelog is included.
				_("\nWhats new in {version}:").format(version=bundle.manifest["version"]),
				changelogText
			))

		if (
			gui.messageBox(
				overwriteExistingAddonInstallationMessage
				if curVersion == newVersion
				else updateAddonInstallationMessage,
				messageBoxTitle,
				wx.YES | wx.NO | wx.ICON_WARNING,
			)
			!= wx.YES
		):
			docAddon.completeRemove(runUninstallTask=False)
			return False
# End of #14041 modifications

	return gui.addonGui._performExternalAddonBundleInstall(parentWindow, bundle, prevAddon)

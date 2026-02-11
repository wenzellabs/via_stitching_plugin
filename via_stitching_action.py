"""
KiCad ActionPlugin that adds a toolbar button and displays a dialog with checkboxes.
"""
import os

try:
    import wx
    import pcbnew
except Exception:
    # When this module is inspected outside KiCad, imports may fail. Allow that.
    wx = None
    pcbnew = None


class ViaStitchingDialog(wx.Dialog):
    def __init__(self, parent=None):
        super(ViaStitchingDialog, self).__init__(parent, title="Via Stitching", size=(400, 280))

        self.panel = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # Instruction
        st = wx.StaticText(self.panel, label="Select options:")
        v.Add(st, flag=wx.ALL, border=8)

        # Checkboxes CB1..CB5
        self.cb = []
        cb_labels = [
            'remove all existing GND vias',
            'CB2',
            'CB3',
            'CB4',
            'CB5',
        ]
        for i, label in enumerate(cb_labels, start=1):
            c = wx.CheckBox(self.panel, label=label)
            v.Add(c, flag=wx.LEFT | wx.TOP, border=10)
            self.cb.append(c)

        # Spacer
        v.Add((10, 10), proportion=1)

        # Buttons at bottom
        hs = wx.BoxSizer(wx.HORIZONTAL)
        hs.AddStretchSpacer()
        btn_cancel = wx.Button(self.panel, label="Cancel")
        btn_go = wx.Button(self.panel, label="Go!")
        hs.Add(btn_cancel, flag=wx.RIGHT, border=8)
        hs.Add(btn_go)

        v.Add(hs, flag=wx.EXPAND | wx.ALL, border=8)

        self.panel.SetSizer(v)

        # Events
        btn_cancel.Bind(wx.EVT_BUTTON, self.on_cancel)
        btn_go.Bind(wx.EVT_BUTTON, self.on_go)

    def on_cancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def on_go(self, event):
        # For now just show a summary and close with OK. Real functionality will be
        # implemented later as requested.
        selected = [i + 1 for i, c in enumerate(self.cb) if c.IsChecked()]
        msg = "Selected checkboxes: %s" % (', '.join('CB%d' % s for s in selected) if selected else 'none')
        wx.MessageBox(msg, "Via Stitching", wx.OK | wx.ICON_INFORMATION)
        self.EndModal(wx.ID_OK)


class ViaStitchingPlugin(pcbnew.ActionPlugin if pcbnew is not None else object):
    """ActionPlugin to add a toolbar button and show the dialog.

    In KiCad: place this folder under your KiCad plugins path or add the path to
    the plugin search paths so KiCad imports it at startup. The icon is generated
    on first import.
    """

    def defaults(self):
        # Called by pcbnew to query plugin metadata.
        self.name = "Via Stitching"
        self.category = "Modify PCB"
        self.description = "Tools for via stitching (UI skeleton)."

        # Icon path (place via_icon.png next to this file)
        this_dir = os.path.dirname(__file__)
        icon_path = os.path.join(this_dir, 'via_icon.png')
        if os.path.exists(icon_path):
            self.icon_file_name = icon_path
        else:
            self.icon_file_name = ''

        # Show toolbar button in the PCB editor
        try:
            self.show_toolbar_button = True
        except Exception:
            pass

    def Run(self):
        # Show the dialog in the PCB editor context
        if wx is None:
            print('ViaStitchingPlugin: wx not available, cannot display dialog.')
            return

        # Don't pass a parent to avoid bringing other windows to front
        dlg = ViaStitchingDialog(parent=None)
        res = dlg.ShowModal()
        dlg.Destroy()

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

        # Checkboxes with descriptive internal names
        self.cb_remove_existing_vias = wx.CheckBox(self.panel, label='remove all existing GND vias')
        self.cb_option2 = wx.CheckBox(self.panel, label='CB2')
        self.cb_option3 = wx.CheckBox(self.panel, label='CB3')
        self.cb_option4 = wx.CheckBox(self.panel, label='CB4')
        self.cb_option5 = wx.CheckBox(self.panel, label='CB5')
        
        v.Add(self.cb_remove_existing_vias, flag=wx.LEFT | wx.TOP, border=10)
        v.Add(self.cb_option2, flag=wx.LEFT | wx.TOP, border=10)
        v.Add(self.cb_option3, flag=wx.LEFT | wx.TOP, border=10)
        v.Add(self.cb_option4, flag=wx.LEFT | wx.TOP, border=10)
        v.Add(self.cb_option5, flag=wx.LEFT | wx.TOP, border=10)

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
        # Execute selected actions
        try:
            board = pcbnew.GetBoard()
            if board is None:
                wx.MessageBox("No board loaded.", "Error", wx.OK | wx.ICON_ERROR, self)
                self.EndModal(wx.ID_CANCEL)
                return
            
            messages = []
            
            if self.cb_remove_existing_vias.IsChecked():
                count = self.remove_gnd_vias(board)
                if count >= 0:
                    messages.append("Removed %d GND vias." % count)
            
            # Placeholder for other options
            # if self.cb_option2.IsChecked():
            #     result = self.do_option2(board)
            #     messages.append(result)
            # etc.
            
            if messages:
                msg = "\n".join(messages) + "\n\nOperation completed successfully."
                wx.MessageBox(msg, "Via Stitching", wx.OK | wx.ICON_INFORMATION, self)
            
            self.EndModal(wx.ID_OK)
        except Exception as e:
            wx.MessageBox("Error: %s" % str(e), "Error", wx.OK | wx.ICON_ERROR, self)
            self.EndModal(wx.ID_CANCEL)
    
    def remove_gnd_vias(self, board):
        """Remove all vias connected to GND net.
        
        Returns: number of vias removed, or -1 if GND net not found.
        """
        if pcbnew is None:
            return -1
        
        # Find the GND net
        gnd_net = None
        gnd_net_code = -1
        netinfo = board.GetNetInfo()
        
        # Iterate through all nets to find GND
        for net_code in range(netinfo.GetNetCount()):
            net = netinfo.GetNetItem(net_code)
            if net is not None:
                net_name = net.GetNetname().upper()
                if net_name in ['GND', 'GROUND', 'VSS']:
                    gnd_net = net
                    gnd_net_code = net.GetNetCode()
                    break
        
        if gnd_net is None:
            wx.MessageBox("No GND net found in the board.", "Info", wx.OK | wx.ICON_INFORMATION, self)
            return -1
        
        # Collect vias to remove
        vias_to_remove = []
        for track in board.GetTracks():
            # Check if it's a via - in KiCad Python API
            if hasattr(track, 'GetViaType') or track.Type() == pcbnew.PCB_VIA_T:
                # Check net by net code
                if track.GetNetCode() == gnd_net_code:
                    vias_to_remove.append(track)
        
        # Remove the vias
        for via in vias_to_remove:
            board.Remove(via)
        
        # Refresh the board
        pcbnew.Refresh()
        
        return len(vias_to_remove)


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

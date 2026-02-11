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
        super(ViaStitchingDialog, self).__init__(parent, title="Via Stitching")

        self.panel = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # Instruction
        st = wx.StaticText(self.panel, label="Select options:")
        v.Add(st, flag=wx.ALL, border=8)

        # Checkboxes with descriptive internal names
        self.cb_remove_existing_vias = wx.CheckBox(self.panel, label='remove all existing GND vias')
        self.cb_stitch_top = wx.CheckBox(self.panel, label='stitch around top traces')
        self.cb_stitch_inner = wx.CheckBox(self.panel, label='stitch around inner traces')
        self.cb_stitch_bot = wx.CheckBox(self.panel, label='stitch around bottom traces')
        
        # Set default checked states
        self.cb_stitch_top.SetValue(True)
        self.cb_stitch_inner.SetValue(True)
        self.cb_stitch_bot.SetValue(True)
        
        v.Add(self.cb_remove_existing_vias, flag=wx.LEFT | wx.TOP, border=10)
        v.Add(self.cb_stitch_top, flag=wx.LEFT | wx.TOP, border=10)
        v.Add(self.cb_stitch_inner, flag=wx.LEFT | wx.TOP, border=10)
        v.Add(self.cb_stitch_bot, flag=wx.LEFT | wx.TOP, border=10)
        
        # Numeric parameters
        params_sizer = wx.FlexGridSizer(rows=3, cols=3, hgap=5, vgap=8)
        
        # Stitch distance
        lbl_distance = wx.StaticText(self.panel, label="stitch distance along traces:")
        self.txt_stitch_distance = wx.TextCtrl(self.panel, value="10.0", size=(80, -1))
        lbl_distance_unit = wx.StaticText(self.panel, label="mm")
        params_sizer.Add(lbl_distance, flag=wx.ALIGN_CENTER_VERTICAL)
        params_sizer.Add(self.txt_stitch_distance, flag=wx.ALIGN_CENTER_VERTICAL)
        params_sizer.Add(lbl_distance_unit, flag=wx.ALIGN_CENTER_VERTICAL)
        
        # Via drill
        lbl_drill = wx.StaticText(self.panel, label="via drill:")
        self.txt_via_drill = wx.TextCtrl(self.panel, value="0.3", size=(80, -1))
        lbl_drill_unit = wx.StaticText(self.panel, label="mm")
        params_sizer.Add(lbl_drill, flag=wx.ALIGN_CENTER_VERTICAL)
        params_sizer.Add(self.txt_via_drill, flag=wx.ALIGN_CENTER_VERTICAL)
        params_sizer.Add(lbl_drill_unit, flag=wx.ALIGN_CENTER_VERTICAL)
        
        # Via diameter
        lbl_diameter = wx.StaticText(self.panel, label="via diameter:")
        self.txt_via_diameter = wx.TextCtrl(self.panel, value="0.6", size=(80, -1))
        lbl_diameter_unit = wx.StaticText(self.panel, label="mm")
        params_sizer.Add(lbl_diameter, flag=wx.ALIGN_CENTER_VERTICAL)
        params_sizer.Add(self.txt_via_diameter, flag=wx.ALIGN_CENTER_VERTICAL)
        params_sizer.Add(lbl_diameter_unit, flag=wx.ALIGN_CENTER_VERTICAL)
        
        v.Add(params_sizer, flag=wx.LEFT | wx.TOP | wx.RIGHT, border=10)

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
        
        # Auto-size dialog to fit all content
        v.Fit(self.panel)
        self.Fit()
        self.SetMinSize((400, -1))

        # Events
        btn_cancel.Bind(wx.EVT_BUTTON, self.on_cancel)
        btn_go.Bind(wx.EVT_BUTTON, self.on_go)

    def on_cancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def on_go(self, event):
        # Execute selected actions
        MIN_VIA_RING = 0.1
        
        try:
            board = pcbnew.GetBoard()
            if board is None:
                wx.MessageBox("No board loaded.", "Error", wx.OK | wx.ICON_ERROR, self)
                self.EndModal(wx.ID_CANCEL)
                return
            
            # Parse numeric parameters
            try:
                stitch_distance = float(self.txt_stitch_distance.GetValue())
                via_drill = float(self.txt_via_drill.GetValue())
                via_diameter = float(self.txt_via_diameter.GetValue())
            except ValueError:
                wx.MessageBox("Invalid numeric values. Please enter valid numbers.", "Error", wx.OK | wx.ICON_ERROR, self)
                self.EndModal(wx.ID_CANCEL)
                return
            
            # Validate via ring size
            via_ring = (via_diameter - via_drill) / 2.0
            if via_ring < MIN_VIA_RING:
                wx.MessageBox(
                    "Via ring too small!\n\n"
                    "Via diameter - Via drill = %.3f mm\n"
                    "Ring width = %.3f mm\n"
                    "Minimum required = %.2f mm\n\n"
                    "Please increase via diameter or decrease drill size." % 
                    (via_diameter - via_drill, via_ring, MIN_VIA_RING),
                    "Error", wx.OK | wx.ICON_ERROR, self)
                self.EndModal(wx.ID_CANCEL)
                return
            
            messages = []
            
            if self.cb_remove_existing_vias.IsChecked():
                count = self.remove_gnd_vias(board)
                if count >= 0:
                    messages.append("Removed %d GND vias.\n" % count)
            
            # Gather traces per layer for stitching
            traces_per_layer = {}
            if self.cb_stitch_top.IsChecked() or self.cb_stitch_inner.IsChecked() or self.cb_stitch_bot.IsChecked():
                traces_per_layer = self.gather_traces_per_layer(board, 
                                                                  self.cb_stitch_top.IsChecked(),
                                                                  self.cb_stitch_inner.IsChecked(),
                                                                  self.cb_stitch_bot.IsChecked())
                
                # Report trace counts in top-to-bottom layer order
                layer_order = self.get_layer_order(board, traces_per_layer.keys())
                
                messages.append("Traces (single straight elements):")
                for layer_name in layer_order:
                    if layer_name in traces_per_layer:
                        messages.append("  Layer %s: %d traces found" % (layer_name, len(traces_per_layer[layer_name])))
                
                # Reconstruct tracks from trace segments
                tracks_per_layer = {}
                longest_track = None
                longest_track_layer = None
                max_trace_count = 0
                
                messages.append("\nTracks:")
                for layer_name in layer_order:
                    if layer_name in traces_per_layer:
                        tracks = self.reconstruct_tracks(traces_per_layer[layer_name])
                        tracks_per_layer[layer_name] = tracks
                        messages.append("  Layer %s: %d tracks reconstructed" % (layer_name, len(tracks)))
                        
                        # Find longest track
                        for track in tracks:
                            if len(track) > max_trace_count:
                                max_trace_count = len(track)
                                longest_track = track
                                longest_track_layer = layer_name
                
                if longest_track:
                    messages.append("\nLongest track: %d traces on layer %s (selected)" % (max_trace_count, longest_track_layer))
                    # Select all traces in the longest track
                    for trace in longest_track:
                        trace.SetSelected()
                    pcbnew.Refresh()
            
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
    
    def gather_traces_per_layer(self, board, include_top, include_inner, include_bot):
        """Gather all traces organized by layer.
        
        Args:
            board: pcbnew board object
            include_top: whether to include top layer
            include_inner: whether to include inner layers
            include_bot: whether to include bottom layer
            
        Returns:
            dict mapping layer name to list of trace objects
        """
        if pcbnew is None:
            return {}
        
        traces_per_layer = {}
        
        # Get layer IDs
        top_layer = pcbnew.F_Cu
        bottom_layer = pcbnew.B_Cu
        
        # Determine which layers to process
        layers_to_process = set()
        if include_top:
            layers_to_process.add(top_layer)
        if include_bot:
            layers_to_process.add(bottom_layer)
        
        if include_inner:
            # Add all inner copper layers
            layer_count = board.GetCopperLayerCount()
            for i in range(1, layer_count - 1):  # Skip top (0) and bottom (layer_count-1)
                layers_to_process.add(pcbnew.In1_Cu + (i - 1) * 2)
        
        # Collect traces
        for track in board.GetTracks():
            # Skip vias - we only want tracks
            if hasattr(track, 'GetViaType') or track.Type() == pcbnew.PCB_VIA_T:
                continue
            
            track_layer = track.GetLayer()
            if track_layer in layers_to_process:
                layer_name = board.GetLayerName(track_layer)
                if layer_name not in traces_per_layer:
                    traces_per_layer[layer_name] = []
                traces_per_layer[layer_name].append(track)
        
        return traces_per_layer
    
    def get_layer_order(self, board, layer_names):
        """Sort layer names in top-to-bottom order.
        
        Args:
            board: pcbnew board object
            layer_names: iterable of layer name strings
            
        Returns:
            list of layer names sorted from top to bottom
        """
        if pcbnew is None:
            return sorted(layer_names)
        
        # Create a mapping of layer name to layer ID
        layer_map = {}
        for name in layer_names:
            # Find the layer ID for this name
            for layer_id in range(pcbnew.PCB_LAYER_ID_COUNT):
                if board.GetLayerName(layer_id) == name:
                    layer_map[name] = layer_id
                    break
        
        # Sort by layer ID (lower IDs are towards the top)
        return sorted(layer_names, key=lambda name: layer_map.get(name, 999))
    
    def reconstruct_tracks(self, traces):
        """Reconstruct complete tracks from individual trace segments.
        
        Trace segments that share endpoints and belong to the same net are grouped
        into tracks (complete connection paths).
        
        Args:
            traces: list of trace objects on a single layer
            
        Returns:
            list of tracks, where each track is a list of connected trace objects
        """
        if pcbnew is None or not traces:
            return []
        
        COORD_TOLERANCE = 1000  # nanometers (1 micron tolerance)
        
        # Mark which traces have been processed
        processed = [False] * len(traces)
        tracks = []
        
        def coords_match(pos1, pos2):
            """Check if two positions match within tolerance."""
            return (abs(pos1.x - pos2.x) <= COORD_TOLERANCE and 
                    abs(pos1.y - pos2.y) <= COORD_TOLERANCE)
        
        def find_connected_trace(trace, endpoint, start_idx):
            """Find a trace starting from start_idx that connects to the given endpoint.
            
            Only searches forward from start_idx to avoid redundant comparisons.
            """
            for i in range(start_idx, len(traces)):
                if processed[i]:
                    continue
                    
                other = traces[i]
                if other == trace:
                    continue
                    
                other_start = other.GetStart()
                other_end = other.GetEnd()
                
                # Check if endpoint matches either end of the other trace
                if coords_match(endpoint, other_start) or coords_match(endpoint, other_end):
                    # Verify same net
                    if trace.GetNetCode() != other.GetNetCode():
                        raise Exception(
                            "Net mismatch! Traces share endpoint but have different nets:\n"
                            "Net %s vs Net %s" % (trace.GetNetname(), other.GetNetname())
                        )
                    return i, other
            return None, None
        
        # Build tracks by following connected traces
        for seed_idx in range(len(traces)):
            if processed[seed_idx]:
                continue
                
            seed_trace = traces[seed_idx]
            processed[seed_idx] = True
            current_track = [seed_trace]
            
            # Grow the track in both directions
            # Direction 1: from seed_trace's end
            current_trace = seed_trace
            current_endpoint = seed_trace.GetEnd()
            while True:
                idx, next_trace = find_connected_trace(current_trace, current_endpoint, seed_idx + 1)
                if next_trace is None:
                    break
                processed[idx] = True
                current_track.append(next_trace)
                # Move to the far end of the next trace
                if coords_match(current_endpoint, next_trace.GetStart()):
                    current_endpoint = next_trace.GetEnd()
                else:
                    current_endpoint = next_trace.GetStart()
                current_trace = next_trace
            
            # Direction 2: from original seed_trace's start
            current_trace = seed_trace
            current_endpoint = seed_trace.GetStart()
            while True:
                idx, next_trace = find_connected_trace(current_trace, current_endpoint, seed_idx + 1)
                if next_trace is None:
                    break
                processed[idx] = True
                current_track.insert(0, next_trace)
                # Move to the far end of the next trace
                if coords_match(current_endpoint, next_trace.GetStart()):
                    current_endpoint = next_trace.GetEnd()
                else:
                    current_endpoint = next_trace.GetStart()
                current_trace = next_trace
            
            tracks.append(current_track)
        
        return tracks


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

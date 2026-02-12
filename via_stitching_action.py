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
                
                messages.append("\nTracks:")
                for layer_name in layer_order:
                    if layer_name in traces_per_layer:
                        tracks = self.reconstruct_tracks(traces_per_layer[layer_name])
                        tracks_per_layer[layer_name] = tracks
                        messages.append("  Layer %s: %d tracks reconstructed" % (layer_name, len(tracks)))
                
                # Collect all copper obstacles once for all layers
                copper_obstacles = self.get_copper_obstacles(board)
                
                # Place stitching vias along tracks
                total_vias_placed = 0
                total_vias_skipped = 0
                for layer_name in layer_order:
                    if layer_name in tracks_per_layer:
                        layer_id = self.get_layer_id(board, layer_name)
                        vias_placed, vias_skipped = self.stitch_tracks(board, tracks_per_layer[layer_name], 
                                                         layer_id, stitch_distance, 
                                                         via_drill, via_diameter, copper_obstacles)
                        total_vias_placed += vias_placed
                        total_vias_skipped += vias_skipped
                
                if total_vias_placed > 0:
                    total_attempted = total_vias_placed + total_vias_skipped
                    success_rate = (total_vias_placed * 100.0) / total_attempted if total_attempted > 0 else 0
                    messages.append(f"\n{total_vias_placed} stitching vias placed")
                    messages.append(f"{total_vias_skipped} vias skipped (clearance issues)")
                    messages.append(f"Success rate: {success_rate:.1f}%")
                    
                    if total_vias_skipped > total_vias_placed:
                        messages.append("\nNote: Many vias were skipped due to insufficient clearance.")
                        messages.append("This usually means the PCB is very dense in those areas.")
                        messages.append("Consider using smaller vias or increasing trace spacing.")
            
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
    
    def get_layer_id(self, board, layer_name):
        """Get layer ID from layer name."""
        if pcbnew is None:
            return 0
        for layer_id in range(pcbnew.PCB_LAYER_ID_COUNT):
            if board.GetLayerName(layer_id) == layer_name:
                return layer_id
        return 0
    
    def stitch_tracks(self, board, tracks, layer_id, stitch_distance_mm, via_drill_mm, via_diameter_mm, copper_obstacles):
        """Place stitching vias along tracks.
        
        Args:
            board: pcbnew board object
            tracks: list of tracks (each track is a list of trace segments)
            layer_id: layer ID for the traces
            stitch_distance_mm: distance between via placements in mm
            via_drill_mm: via drill diameter in mm
            via_diameter_mm: via diameter in mm
            copper_obstacles: precomputed copper obstacles dict
            
        Returns:
            tuple: (number of vias placed, number of vias skipped)
        """
        if pcbnew is None:
            return 0
        
        import math
        
        # Convert mm to internal units (nanometers)
        stitch_distance = int(stitch_distance_mm * 1e6)
        via_drill = int(via_drill_mm * 1e6)
        via_diameter = int(via_diameter_mm * 1e6)
        
        # Find GND net
        gnd_net = None
        netinfo = board.GetNetInfo()
        for net_code in range(netinfo.GetNetCount()):
            net = netinfo.GetNetItem(net_code)
            if net is not None:
                net_name = net.GetNetname().upper()
                if net_name in ['GND', 'GROUND', 'VSS']:
                    gnd_net = net
                    break
        
        if gnd_net is None:
            return 0
        
        vias_placed = 0
        vias_skipped = 0
        
        # Track vias per net for debug
        vias_per_net = {}
        
        # Collect all courtyards (front and back) for collision detection
        courtyards = self.get_all_courtyards(board)
        
        # Collect all length tuning areas for collision detection
        tuning_areas = self.get_all_tuning_areas(board)
        
        for track in tracks:
            if not track:
                continue
            
            # Get the first trace to determine net class clearance and trace width
            first_trace = track[0]
            track_net = first_trace.GetNet()
            
            # Find the maximum trace width in the track (handles mixed-width tracks)
            trace_width = max(trace.GetWidth() for trace in track)
            
            # Initialize via counter for this net
            if track_net:
                net_name = track_net.GetNetname()
                if net_name not in vias_per_net:
                    vias_per_net[net_name] = 0
            
            # Get clearance - use the board's design rules
            # GetClearance() method on tracks returns the actual clearance for that object
            try:
                clearance = first_trace.GetOwnClearance(layer_id)
            except:
                # Fallback: try different methods or use default
                try:
                    clearance = board.GetDesignSettings().GetDefault().GetClearance()
                except:
                    clearance = 200000  # default 0.2mm in nanometers
            
            # Check if this is a differential pair - if so, add extra offset for the pair spacing
            # Differential pairs need vias placed outside the pair, not between the traces
            # In KiCAD 9, we need to detect diff pairs by looking for adjacent traces with similar names
            diff_pair_gap = 0
            
            # Try to find the paired trace (e.g., USB2_N <-> USB2_P)
            if track_net:
                net_name = track_net.GetNetname()
                # Check if this looks like a differential pair net name
                if net_name.endswith('_N') or net_name.endswith('_P'):
                    # Find the opposite net
                    if net_name.endswith('_N'):
                        pair_name = net_name[:-2] + '_P'
                    else:
                        pair_name = net_name[:-2] + '_N'
                    
                    # Find the closest trace on the paired net to estimate gap
                    # Look through all tracks to find traces from the paired net
                    min_gap = float('inf')
                    for other_track in tracks:
                        if other_track and other_track != track:
                            other_net = other_track[0].GetNet()
                            if other_net and other_net.GetNetname() == pair_name:
                                # Found the paired net, measure gap between traces
                                for trace1 in track:
                                    for trace2 in other_track:
                                        # Calculate approximate distance between traces
                                        # This is simplified - just center-to-center of closest segments
                                        p1 = trace1.GetStart()
                                        p2 = trace2.GetStart()
                                        dx = p2.x - p1.x
                                        dy = p2.y - p1.y
                                        dist = math.sqrt(dx*dx + dy*dy)
                                        if dist < min_gap:
                                            min_gap = dist
                    
                    if min_gap < float('inf'):
                        # Subtract both trace widths to get the actual gap between edges
                        # min_gap is center-to-center distance
                        # gap = center_to_center - (width1/2 + width2/2) - (width1/2 + width2/2)
                        #     = center_to_center - width1 - width2
                        # For same width traces: gap = center_to_center - 2*trace_width
                        diff_pair_gap = int(min_gap - 2 * trace_width)
            
            # Calculate offset from track center to via center
            # For single traces: offset = trace_width/2 + clearance + via_diameter/2
            #   This places the via edge at clearance distance from the trace edge
            # For differential pairs: offset = trace_width/2 + clearance + diff_pair_gap + trace_width + clearance + via_diameter/2
            #   This places the via outside the differential pair, with clearance to the paired trace
            if diff_pair_gap > 0:
                # Differential pair: go past own trace edge, clearance, gap, other trace, clearance, via radius
                offset = (trace_width // 2) + clearance + diff_pair_gap + trace_width + clearance + (via_diameter // 2)
            else:
                # Single trace: half trace width + clearance + via radius
                offset = trace_width // 2 + clearance + via_diameter // 2
            
            # First, sort traces in the track to ensure they're in sequence
            # (assuming they should connect end-to-start)
            sorted_track = self.sort_track_traces(track)
            
            # Walk along the entire track, accumulating distance
            total_distance = 0
            next_via_distance = 0  # Place first vias at the start
            
            for trace in sorted_track:
                start = trace.GetStart()
                end = trace.GetEnd()
                
                # Calculate trace length and direction
                dx = end.x - start.x
                dy = end.y - start.y
                length = math.sqrt(dx*dx + dy*dy)
                
                if length < 1:
                    continue
                
                # Unit direction vector
                dir_x = dx / length
                dir_y = dy / length
                
                # Recalculate offset for this segment's actual trace width
                # For differential pairs: Add extra half trace width to avoid the paired trace
                #   offset = trace_width/2 + clearance + via_diameter/2 + (trace_width/2 if diff pair)
                #   The collision detection will block vias too close to paired trace
                # For single traces: offset = trace_width/2 + effective_clearance + via_diameter/2
                #   Use minimum 0.2mm clearance for better same-net spacing
                if diff_pair_gap > 0:
                    # Differential pair: add half trace width to push vias away from paired trace
                    segment_offset = trace_width // 2 + clearance + via_diameter // 2 + trace_width // 2
                else:
                    # Single trace: use minimum 0.2mm clearance for same-net spacing
                    effective_clearance = max(clearance, int(0.2e6))  # 0.2mm minimum
                    segment_offset = trace_width // 2 + effective_clearance + via_diameter // 2
                
                # Perpendicular vector (rotated 90° counterclockwise)
                perp_x = -dir_y
                perp_y = dir_x
                
                # Check if we need to place vias along this trace segment
                segment_start_distance = total_distance
                segment_end_distance = total_distance + length
                
                while next_via_distance < segment_end_distance:
                    # Calculate position along this specific trace segment
                    dist_along_segment = next_via_distance - segment_start_distance
                    
                    if dist_along_segment >= 0:  # Via position is within this segment
                        pos_x = round(start.x + dir_x * dist_along_segment)
                        pos_y = round(start.y + dir_y * dist_along_segment)
                        
                        # Place two vias: one on each side (independently)
                        # Use segment_offset which is calculated for this segment's actual width
                        for side in [-1, 1]:
                            via_x = round(pos_x + perp_x * segment_offset * side)
                            via_y = round(pos_y + perp_y * segment_offset * side)
                            
                            # Check if via would collide with any courtyard
                            # Since vias are through-holes, they must avoid ALL courtyards (F and B)
                            if self.via_collides_with_courtyards(via_x, via_y, via_diameter, courtyards):
                                vias_skipped += 1
                                continue  # Skip this via
                            
                            # Check if via would collide with any length tuning area
                            if self.via_collides_with_tuning_areas(via_x, via_y, via_diameter, tuning_areas):
                                vias_skipped += 1
                                continue  # Skip this via
                            
                            # Check if via would collide with any copper on any layer
                            # IMPORTANT: Only exclude the current trace segment we're stitching along
                            # NOT the entire track - this ensures vias stay clear of length tuning wiggles
                            # that are part of the same connected track but on different segments
                            collision_result = self.via_collides_with_copper(via_x, via_y, via_diameter, copper_obstacles, clearance, track_net, [trace])
                            if collision_result:
                                vias_skipped += 1
                                continue  # Skip this via
                            
                            # Create via
                            via = pcbnew.PCB_VIA(board)
                            via.SetPosition(pcbnew.VECTOR2I(via_x, via_y))
                            via.SetDrill(via_drill)
                            via.SetWidth(via_diameter)
                            via.SetNet(gnd_net)
                            
                            # Set via to span all layers (through via)
                            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                            
                            board.Add(via)
                            vias_placed += 1
                            
                            # Track vias per net
                            if track_net:
                                vias_per_net[track_net.GetNetname()] += 1
                            
                            # Add this via to copper_obstacles so future vias avoid it
                            # Since these are GND vias, they'll checked with same-net clearance
                            # which is reduced compared to different-net clearance
                            for layer in copper_obstacles.keys():
                                copper_obstacles[layer].append(via)
                    
                    # Move to next stitch position
                    next_via_distance += stitch_distance
                
                # Update total distance for next trace
                total_distance = segment_end_distance
        
        # Refresh board
        pcbnew.Refresh()
        
        return vias_placed, vias_skipped
    
    def sort_track_traces(self, track):
        """Sort traces in a track so they form a continuous path.
        
        Args:
            track: list of trace objects that should connect end-to-end
            
        Returns:
            sorted list of traces forming a continuous path
        """
        if not track or len(track) <= 1:
            return track
        
        COORD_TOLERANCE = 1000  # nanometers
        
        def coords_match(pos1, pos2):
            return (abs(pos1.x - pos2.x) <= COORD_TOLERANCE and 
                    abs(pos1.y - pos2.y) <= COORD_TOLERANCE)
        
        sorted_traces = [track[0]]
        remaining = list(track[1:])
        
        # Build chain by finding traces that connect to current endpoint
        while remaining:
            current_end = sorted_traces[-1].GetEnd()
            found = False
            
            for i, trace in enumerate(remaining):
                if coords_match(current_end, trace.GetStart()):
                    sorted_traces.append(trace)
                    remaining.pop(i)
                    found = True
                    break
                elif coords_match(current_end, trace.GetEnd()):
                    # Trace is backwards - we'll handle this by just using it as-is
                    # The via placement will still work
                    sorted_traces.append(trace)
                    remaining.pop(i)
                    found = True
                    break
            
            if not found:
                # Try connecting to the start of the chain instead
                current_start = sorted_traces[0].GetStart()
                for i, trace in enumerate(remaining):
                    if coords_match(current_start, trace.GetEnd()):
                        sorted_traces.insert(0, trace)
                        remaining.pop(i)
                        found = True
                        break
                    elif coords_match(current_start, trace.GetStart()):
                        sorted_traces.insert(0, trace)
                        remaining.pop(i)
                        found = True
                        break
            
            if not found:
                # Disconnected trace - just append remaining
                sorted_traces.extend(remaining)
                break
        
        return sorted_traces
    
    def get_all_courtyards(self, board):
        """Collect all courtyard polygons from footprints (front and back).
        
        Args:
            board: pcbnew board object
            
        Returns:
            list of courtyard shape objects
        """
        if pcbnew is None:
            return []
        
        courtyards = []
        
        for footprint in board.GetFootprints():
            # Get both front and back courtyards - vias must avoid both!
            for layer in [pcbnew.F_CrtYd, pcbnew.B_CrtYd]:
                # Get courtyard outlines for this layer
                try:
                    # Try getting the courtyard polygon directly
                    courtyard_poly = footprint.GetCourtyard(layer)
                    if courtyard_poly and courtyard_poly.OutlineCount() > 0:
                        courtyards.append((layer, courtyard_poly))
                except:
                    # Fallback: iterate through graphical items
                    for item in footprint.GraphicalItems():
                        if item.GetLayer() == layer:
                            courtyards.append((layer, item))
        
        return courtyards
    
    def via_collides_with_courtyards(self, via_x, via_y, via_diameter, courtyards):
        """Check if a via at given position would collide with any courtyard.
        
        A collision occurs if:
        - The via center is inside a courtyard, OR
        - Any part of the via (center + radius) overlaps with a courtyard
        
        Args:
            via_x, via_y: via center position in internal units (nanometers)
            via_diameter: via diameter in internal units
            courtyards: list of (layer, courtyard_object) tuples
            
        Returns:
            True if collision detected, False otherwise
        """
        if pcbnew is None or not courtyards:
            return False
        
        import math
        
        via_radius = via_diameter // 2
        via_pos = pcbnew.VECTOR2I(via_x, via_y)
        
        for courtyard_data in courtyards:
            # Handle both tuple format (layer, object) and plain object
            if isinstance(courtyard_data, tuple):
                layer, courtyard = courtyard_data
            else:
                courtyard = courtyard_data
            
            # Check if this is a SHAPE_POLY_SET (from GetCourtyard)
            if hasattr(courtyard, 'OutlineCount'):
                try:
                    # Check if point is inside the polygon
                    if courtyard.Contains(via_pos):
                        return True
                    
                    # Also check bounding box with margin
                    bbox = courtyard.BBox()
                    if (via_x - via_radius < bbox.GetRight() and
                        via_x + via_radius > bbox.GetLeft() and
                        via_y - via_radius < bbox.GetBottom() and
                        via_y + via_radius > bbox.GetTop()):
                        # Close enough to warrant detailed check
                        # Check distance to outline
                        for outline_idx in range(courtyard.OutlineCount()):
                            outline = courtyard.Outline(outline_idx)
                            for pt_idx in range(outline.PointCount()):
                                pt = outline.CPoint(pt_idx)
                                dx = via_x - pt.x
                                dy = via_y - pt.y
                                dist = math.sqrt(dx*dx + dy*dy)
                                if dist < via_radius:
                                    return True
                except Exception as e:
                    # If anything fails, be conservative
                    pass
            
            # Check different shape types for graphical items
            if hasattr(courtyard, 'GetShape'):
                shape = courtyard.GetShape()
                
                # For rectangle shapes
                if shape == pcbnew.SHAPE_T_RECT:
                    bbox = courtyard.GetBoundingBox()
                    # Expand bounding box by via radius
                    if (via_x - via_radius < bbox.GetRight() and
                        via_x + via_radius > bbox.GetLeft() and
                        via_y - via_radius < bbox.GetBottom() and
                        via_y + via_radius > bbox.GetTop()):
                        return True
                
                # For polygon/polyline shapes
                elif shape == pcbnew.SHAPE_T_POLY:
                    try:
                        # Check if via center is inside polygon
                        if courtyard.HitTest(via_pos):
                            return True
                        
                        # Check if via edge gets close to polygon boundary
                        bbox = courtyard.GetBoundingBox()
                        if (via_x - via_radius < bbox.GetRight() and
                            via_x + via_radius > bbox.GetLeft() and
                            via_y - via_radius < bbox.GetBottom() and
                            via_y + via_radius > bbox.GetTop()):
                            return True
                    except:
                        pass
                
                # For circle shapes
                elif shape == pcbnew.SHAPE_T_CIRCLE:
                    try:
                        center = courtyard.GetCenter()
                        radius = courtyard.GetRadius()
                        dx = via_x - center.x
                        dy = via_y - center.y
                        dist = math.sqrt(dx*dx + dy*dy)
                        if dist < radius + via_radius:
                            return True
                    except:
                        pass
            
            # Fallback: check bounding box with via radius margin
            try:
                bbox = courtyard.GetBoundingBox()
                if (via_x - via_radius < bbox.GetRight() and
                    via_x + via_radius > bbox.GetLeft() and
                    via_y - via_radius < bbox.GetBottom() and
                    via_y + via_radius > bbox.GetTop()):
                    return True
            except:
                pass
        
        return False
    
    def get_all_tuning_areas(self, board):
        """Collect all length tuning pattern areas.
        
        NOTE: We don't need special detection for length tuning patterns.
        The via collision detection already avoids placing vias on or too close to
        ANY tracks (including squiggly length tuning tracks). This function exists
        for potential future enhancements but returns an empty list since we handle
        track collision comprehensively.
        
        Args:
            board: pcbnew board object
            
        Returns:
            list of bounding box tuples (left, top, right, bottom) in internal units
        """
        # Return empty - track collision detection handles everything
        return []
    
    def via_collides_with_tuning_areas(self, via_x, via_y, via_diameter, tuning_areas):
        """Check if a via at given position would collide with any length tuning area.
        
        Args:
            via_x, via_y: via center position in internal units (nanometers)
            via_diameter: via diameter in internal units
            tuning_areas: list of (left, top, right, bottom) bounding box tuples
            
        Returns:
            True if collision detected, False otherwise
        """
        if not tuning_areas:
            return False
        
        via_radius = via_diameter // 2
        
        for bbox in tuning_areas:
            left, top, right, bottom = bbox
            
            # Check if via overlaps with the tuning area (with via radius margin)
            if (via_x - via_radius < right and
                via_x + via_radius > left and
                via_y - via_radius < bottom and
                via_y + via_radius > top):
                return True
        
        return False
    
    def get_copper_obstacles(self, board):
        """Collect all copper objects on all copper layers that could block via placement.
        
        This includes: tracks, pads, existing vias, filled zones.
        Does NOT include: silkscreen, non-copper layers.
        
        Args:
            board: pcbnew board object
            
        Returns:
            dict mapping layer_id to list of obstacle objects
        """
        if pcbnew is None:
            return {}
        
        obstacles = {}
        
        # Get all copper layer IDs
        copper_layers = []
        layer_count = board.GetCopperLayerCount()
        for i in range(layer_count):
            if i == 0:
                copper_layers.append(pcbnew.F_Cu)
            elif i == layer_count - 1:
                copper_layers.append(pcbnew.B_Cu)
            else:
                # Inner layers
                copper_layers.append(pcbnew.In1_Cu + (i - 1) * 2)
        
        # Initialize obstacle lists for each layer
        for layer in copper_layers:
            obstacles[layer] = []
        
        # Collect tracks and vias
        for track in board.GetTracks():
            if hasattr(track, 'GetViaType') or track.Type() == pcbnew.PCB_VIA_T:
                # Via - affects all layers it spans
                layer_top, layer_bottom = track.GetLayerSet().Seq()[0], track.GetLayerSet().Seq()[-1]
                for layer in copper_layers:
                    obstacles[layer].append(track)
            else:
                # Regular track - only affects its own layer
                track_layer = track.GetLayer()
                if track_layer in obstacles:
                    obstacles[track_layer].append(track)
        
        # Collect pads from all footprints
        for footprint in board.GetFootprints():
            for pad in footprint.Pads():
                # Pads can span multiple layers
                pad_layers = pad.GetLayerSet()
                for layer in copper_layers:
                    if pad_layers.Contains(layer):
                        obstacles[layer].append(pad)
        
        # Zones are NOT added to obstacles - vias can be placed in zones
        # The zone will automatically pour around vias with proper clearance
        
        return obstacles
    
    def via_collides_with_copper(self, via_x, via_y, via_diameter, copper_obstacles, min_clearance, exclude_net, exclude_track=None):
        """Check if a via would collide with any copper on any layer.
        
        Args:
            via_x, via_y: via center in internal units
            via_diameter: via diameter in internal units
            copper_obstacles: dict mapping layer_id to list of copper objects
            min_clearance: minimum clearance required in internal units
            exclude_net: pcbnew net object to exclude from collision check (vias connect to their own net)
            exclude_track: list of trace objects to exclude (the track we're currently stitching)
            
        Returns:
            True if collision detected on ANY layer
        """
        if pcbnew is None or not copper_obstacles:
            return False
        
        import math
        
        # Via footprint = via radius + clearance
        via_radius = via_diameter // 2
        check_radius = via_radius + min_clearance
        
        via_pos = pcbnew.VECTOR2I(via_x, via_y)
        
        # Check all copper layers
        for layer_id, obstacles in copper_obstacles.items():
            for obstacle in obstacles:
                # Skip if this obstacle is part of the track we're stitching
                if exclude_track and obstacle in exclude_track:
                    continue
                
                # Check if this obstacle is on the same net
                obstacle_net = obstacle.GetNet() if hasattr(obstacle, 'GetNet') else None
                same_net = obstacle_net and exclude_net and obstacle_net.GetNetCode() == exclude_net.GetNetCode()
                
                # For obstacles on the same net, we still check clearance but with reduced requirement
                # However, we need enough clearance to not interfere with length tuning patterns
                if same_net:
                    # For same net: via pad radius + clearance to avoid interfering with routing
                    # Use 0.3mm minimum clearance to stay clear of length tuning and other patterns
                    SAME_NET_MIN_CLEARANCE = 300000  # 0.3mm minimum clearance to own traces
                    check_radius_adjusted = via_radius + SAME_NET_MIN_CLEARANCE
                else:
                    # For different nets, use full clearance requirement
                    check_radius_adjusted = check_radius
                
                # Determine obstacle type and check collision
                obstacle_type = obstacle.Type()
                
                # For tracks (including the track we're stitching along - we'll keep clearance)
                if obstacle_type == pcbnew.PCB_TRACE_T:
                    start = obstacle.GetStart()
                    end = obstacle.GetEnd()
                    width = obstacle.GetWidth()
                    
                    # Calculate distance from via center to track segment
                    dist = self.point_to_segment_distance(via_x, via_y, start.x, start.y, end.x, end.y)
                    
                    # Check if too close (via footprint + track half-width)
                    if dist < check_radius_adjusted + width // 2:
                        return True
                
                # For vias
                elif hasattr(obstacle, 'GetViaType') or obstacle_type == pcbnew.PCB_VIA_T:
                    via_pos_other = obstacle.GetPosition()
                    via_diameter_other = obstacle.GetWidth()
                    
                    dx = via_x - via_pos_other.x
                    dy = via_y - via_pos_other.y
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    # Check if vias would overlap
                    # check_radius_adjusted already includes clearance, so just add other via's radius
                    if dist < check_radius_adjusted + via_diameter_other // 2:
                        return True
                
                # For pads (including NPTH mechanical holes)
                elif obstacle_type == pcbnew.PCB_PAD_T:
                    pad_pos = obstacle.GetPosition()
                    
                    dx = via_x - pad_pos.x
                    dy = via_y - pad_pos.y
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    # Get pad size (approximation for circular/oval pads)
                    pad_size = obstacle.GetSize()
                    pad_radius = max(pad_size.x, pad_size.y) // 2
                    
                    # Get pad clearance - pads have their own clearance zones
                    try:
                        pad_clearance = obstacle.GetLocalClearance()
                        if pad_clearance is None or pad_clearance == 0:
                            pad_clearance = min_clearance  # Use default if not set
                    except:
                        pad_clearance = min_clearance
                    
                    # Get soldermask expansion - the soldermask opening is larger than the pad
                    try:
                        soldermask_margin = obstacle.GetSolderMaskExpansion()
                        if soldermask_margin is None:
                            soldermask_margin = 0
                    except:
                        soldermask_margin = 0
                    
                    # Total keepout radius = pad_radius + max(clearance, soldermask_expansion)
                    # We need to stay clear of both the clearance zone AND soldermask opening
                    pad_keepout = max(pad_clearance, abs(soldermask_margin))
                    
                    # Check distance: via_radius + via_clearance + pad_radius + pad_keepout
                    if dist < check_radius_adjusted + pad_radius + pad_keepout:
                        return True
                
                # Zones are NOT checked - vias can be placed in zones
                # The zone will automatically maintain clearance around the via
        
        return False
    
    def point_to_segment_distance(self, px, py, x1, y1, x2, y2):
        """Calculate minimum distance from point (px, py) to line segment (x1,y1)-(x2,y2).
        
        Returns distance in same units as input coordinates.
        """
        import math
        
        # Vector from segment start to point
        dx = px - x1
        dy = py - y1
        
        # Vector of segment
        sx = x2 - x1
        sy = y2 - y1
        
        # Segment length squared
        seg_len_sq = sx*sx + sy*sy
        
        if seg_len_sq == 0:
            # Degenerate segment (point)
            return math.sqrt(dx*dx + dy*dy)
        
        # Project point onto segment (clamped to [0, 1])
        t = max(0, min(1, (dx*sx + dy*sy) / seg_len_sq))
        
        # Closest point on segment
        closest_x = x1 + t * sx
        closest_y = y1 + t * sy
        
        # Distance from point to closest point
        dist_x = px - closest_x
        dist_y = py - closest_y
        
        return math.sqrt(dist_x*dist_x + dist_y*dist_y)


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

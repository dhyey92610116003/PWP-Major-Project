import os
import csv
from datetime import datetime

class DataExporter:
    """Handles exporting complete test metadata and raw data to CSV."""
    
    @staticmethod
    def export_csv(metadata: dict, results: dict, data_points: list = None, arrays: dict = None, filepath: str = None):
        """
        Exports full test data with metadata headers to CSV.
        Can accept either data_points (list of dicts from controller) or arrays (dict from graph).
        """
        # Determine output filepath if not provided
        if not filepath:
            output_dir = "reports"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            sample_id = metadata.get("sample", "Sample").strip().replace(" ", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(output_dir, f"UTM_Data_{sample_id}_{timestamp}.csv")
            
        # Ensure parent directory exists
        parent_dir = os.path.dirname(filepath)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            
        if not filepath.endswith('.csv'):
            filepath += '.csv'

        # Extract data rows
        rows = []
        if data_points and len(data_points) > 0:
            for p in data_points:
                t = p.get('time', 0.0)
                load = p.get('LOAD_kN', 0.0)
                ext = p.get('EXT', 0.0)
                stress = p.get('STRESS', 0.0)
                strain = p.get('STRAIN', 0.0)
                rows.append([f"{t:.2f}", f"{load:.3f}", f"{ext:.3f}", f"{stress:.2f}", f"{strain:.2f}"])
        elif arrays and len(arrays.get("time", [])) > 0:
            times = arrays.get("time", [])
            loads = arrays.get("load", [])
            exts = arrays.get("ext", [])
            stresses = arrays.get("stress", [])
            strains = arrays.get("strain", [])
            
            n = len(times)
            for i in range(n):
                t = times[i] if i < len(times) else 0.0
                load = loads[i] if i < len(loads) else 0.0
                ext = exts[i] if i < len(exts) else 0.0
                stress = stresses[i] if i < len(stresses) else 0.0
                strain = strains[i] if i < len(strains) else 0.0
                rows.append([f"{t:.2f}", f"{load:.3f}", f"{ext:.3f}", f"{stress:.2f}", f"{strain:.2f}"])

        if len(rows) == 0:
            return None

        # Write CSV with complete lab test metadata header
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header block
            writer.writerow(["========================================="])
            writer.writerow(["UTM PROFESSIONAL - MATERIALS TEST REPORT"])
            writer.writerow(["========================================="])
            writer.writerow(["Date & Time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            writer.writerow(["Operator", metadata.get("operator", "N/A")])
            writer.writerow(["Customer", metadata.get("customer", "N/A")])
            writer.writerow(["Sample ID", metadata.get("sample", "N/A")])
            writer.writerow(["Material", metadata.get("material", "N/A")])
            writer.writerow(["Standard", metadata.get("standard", "N/A")])
            
            # Geometry
            w = metadata.get("width", 0.0)
            t = metadata.get("thickness", 0.0)
            area = w * t if (w and t) else 0.0
            g = metadata.get("gauge_length", 0.0)
            writer.writerow(["Width (mm)", f"{w:.2f}"])
            writer.writerow(["Thickness (mm)", f"{t:.2f}"])
            writer.writerow(["Cross-Section Area (mm²)", f"{area:.2f}"])
            writer.writerow(["Gauge Length (mm)", f"{g:.2f}"])
            
            # Key Test Results
            writer.writerow(["Peak Load (kN)", f"{results.get('peak_load', 0.0):.3f}"])
            writer.writerow(["Peak Stress (MPa)", f"{results.get('peak_stress', 0.0):.2f}"])
            writer.writerow([])
            
            # Data table
            writer.writerow(["--- RAW TEST DATA ---"])
            writer.writerow(["Time (s)", "Load (kN)", "Extension (mm)", "Stress (MPa)", "Strain (%)"])
            for row in rows:
                writer.writerow(row)
                
        return filepath

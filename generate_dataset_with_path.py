# generate_dataset_with_path.py - Debug version with key feedback
import cv2
import numpy as np
import csv
import os
from datetime import datetime

def capture_color_samples():
    # --- Select camera index ---
    print("\nAvailable camera indices:")
    print("  0 - Built-in laptop camera (if available)")
    print("  1 - First USB webcam")
    print("  2 - Second USB webcam, etc.")
    cam_index = input("Enter camera index (default 1 for USB webcam): ").strip()
    if cam_index == "":
        cam_index = 1
    else:
        cam_index = int(cam_index)
    
    # --- Show current directory ---
    current_dir = os.getcwd()
    print(f"\nCurrent working directory: {current_dir}")
    print(f"CSV file will be saved here: {current_dir}\\color_dataset.csv")
    
    # --- Ask for save location ---
    change_path = input("\nDo you want to save to a different location? (y/n): ").lower()
    
    if change_path == 'y':
        print("\nOptions:")
        print("1. Desktop")
        print("2. Documents")
        print("3. Custom path")
        choice = input("Choose option (1/2/3): ")
        
        if choice == '1':
            save_dir = os.path.join(os.path.expanduser("~"), "Desktop")
        elif choice == '2':
            save_dir = os.path.join(os.path.expanduser("~"), "Documents")
        elif choice == '3':
            save_dir = input("Enter full path: ")
        else:
            save_dir = current_dir
        
        os.makedirs(save_dir, exist_ok=True)
        print(f"\nFiles will be saved to: {save_dir}")
    else:
        save_dir = current_dir
    
    # --- Initialize webcam ---
    print(f"\nOpening camera index {cam_index}...")
    cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened():
        print(f"Error: Could not open camera index {cam_index}")
        print("Try a different index (0 for built-in, 1 for USB, etc.)")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    samples = []
    sample_count = 0
    roi_size = 50
    
    print("\n=== Color Sample Collection Tool ===")
    print(f"Using camera index: {cam_index}")
    print(f"ROI size: {roi_size}x{roi_size} pixels")
    print("Position the colored object in the center box")
    print("\n⚠️  IMPORTANT: Click on the video window to activate it!")
    print("Then press:")
    print("  'y' for Yellow")
    print("  'o' for Orange")
    print("  'p' for Pink")
    print("  'b' for Blue")
    print("  'g' for Green")
    print("  's' to save and exit")
    print("  'q' to quit without saving")
    print("=====================================\n")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture frame")
            break
        
        h, w = frame.shape[:2]
        center_x, center_y = w // 2, h // 2
        half = roi_size // 2
        roi = frame[center_y - half:center_y + half,
                    center_x - half:center_x + half]
        
        cv2.rectangle(frame, 
                     (center_x - half, center_y - half),
                     (center_x + half, center_y + half),
                     (0, 255, 0), 2)
        
        cv2.putText(frame, f"Samples: {sample_count}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(frame, f"Save to: {os.path.basename(save_dir)}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, "Click here and press y/o/p/b/g", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        cv2.imshow('Capture Color Samples', frame)
        
        # Wait longer for key press (10 ms) and allow window to process events
        key = cv2.waitKey(10) & 0xFF
        
        # Debug: print the key code (for troubleshooting)
        if key != 255:
            print(f"Key pressed: {key} (character: {chr(key) if 32 <= key <= 126 else '?'})")
        
        color_map = {
            ord('y'): 'Yellow',
            ord('o'): 'Orange', 
            ord('p'): 'Pink',
            ord('b'): 'Blue',
            ord('g'): 'Green'
        }
        
        if key in color_map:
            roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            avg_h = np.mean(roi_hsv[:, :, 0])
            avg_s = np.mean(roi_hsv[:, :, 1])
            avg_v = np.mean(roi_hsv[:, :, 2])
            
            color_label = color_map[key]
            samples.append({
                'H': avg_h,
                'S': avg_s,
                'V': avg_v,
                'Label': color_label
            })
            sample_count += 1
            
            print(f"✓ Sample {sample_count}: {color_label} - HSV=({avg_h:.1f}, {avg_s:.1f}, {avg_v:.1f})")
            
            # Flash feedback on screen
            cv2.putText(frame, f"Captured {color_label}!", (w//2-100, h//2),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow('Capture Color Samples', frame)
            cv2.waitKey(200)  # show message briefly
            
        elif key == ord('s'):
            if samples:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"color_dataset_{timestamp}.csv"
                full_path = os.path.join(save_dir, filename)
                default_path = os.path.join(save_dir, "color_dataset.csv")
                
                save_to_csv(samples, full_path)
                save_to_csv(samples, default_path)
                
                print(f"\n✓ Dataset saved to:")
                print(f"  {full_path}")
                print(f"  {default_path}")
                print(f"\nTotal samples: {sample_count}")
                
                color_counts = {}
                for sample in samples:
                    label = sample['Label']
                    color_counts[label] = color_counts.get(label, 0) + 1
                
                print("\nColor distribution:")
                for color, count in color_counts.items():
                    print(f"  {color}: {count} samples")
            else:
                print("\nNo samples to save")
            break
            
        elif key == ord('q'):
            print("\nExiting without saving")
            break
        elif key != 255:
            print(f"Invalid key. Use y, o, p, b, g, s, or q.")
    
    cap.release()
    cv2.destroyAllWindows()

def save_to_csv(samples, filename):
    try:
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['H', 'S', 'V', 'Label']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for sample in samples:
                writer.writerow(sample)
        return True
    except Exception as e:
        print(f"Error saving {filename}: {e}")
        return False

if __name__ == "__main__":
    capture_color_samples()
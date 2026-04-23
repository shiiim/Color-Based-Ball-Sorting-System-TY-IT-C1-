import cv2
import numpy as np
import csv
import os
import time
import socket
from collections import deque
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler

# ==================== CONFIGURATION ====================
ESP32_IP = "10.103.0.239"   
ESP32_PORT = 1234


CAMERA_INDEX = 1             
ROI_SIZE = 90               
PREDICTION_DELAY = 0.5
HSV_SMOOTHING = 5
CONFIDENCE_THRESHOLD = 0.6   

# ==================== CSV LOADING ====================
def load_dataset_from_csv(csv_path=r'C:\Users\shivam\Desktop\color_dataset.csv'):
    """Load dataset from CSV file (expects 4 colors: Green, Orange, Pink, Yellow)"""
    samples = {'H': [], 'S': [], 'V': [], 'Label': []}
    
    if not os.path.exists(csv_path):
        print(f"Dataset file {csv_path} not found.")
        print("Creating balanced sample dataset (4 colors) for demonstration...")
        return create_balanced_sample_dataset()
    
    try:
        with open(csv_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['Label'] == 'Blue':
                    continue
                samples['H'].append(float(row['H']))
                samples['S'].append(float(row['S']))
                samples['V'].append(float(row['V']))
                samples['Label'].append(row['Label'])
        
        print(f"Loaded {len(samples['Label'])} samples from {csv_path}")
        unique = set(samples['Label'])
        print(f"Colors in dataset: {unique}")
        return samples
        
    except Exception as e:
        print(f"Error loading dataset: {e}")
        print("Using balanced sample dataset instead...")
        return create_balanced_sample_dataset()

def create_balanced_sample_dataset():
    samples = {'H': [], 'S': [], 'V': [], 'Label': []}
    ranges = {
         'Yellow': (33, 38,     46, 132,   224, 255),   # H, S, V
        'Orange': (15, 25,     86, 178,   196, 255),
        'Green':  (56, 75,     34, 210,   227, 255),
        'Pink':   (138, 148,   34, 174,   234, 255)
    }
    samples_per_color = 100
    for color, (h_min, h_max, s_min, s_max, v_min, v_max) in ranges.items():
        count = 0
        while count < samples_per_color:
            h = np.random.uniform(h_min, h_max)
            s = np.random.uniform(s_min, s_max)
            v = np.random.uniform(v_min, v_max)
            samples['H'].append(float(h))
            samples['S'].append(float(s))
            samples['V'].append(float(v))
            samples['Label'].append(color)
            count += 1
    print(f"Created BALANCED dataset: {samples_per_color} samples per color → {len(samples['Label'])} total")
    return samples

def train_knn_model(samples):
    if samples is None or len(samples['Label']) == 0:
        print("No samples available for training")
        return None, None
    X = np.column_stack([samples['H'], samples['S'], samples['V']])
    y = np.array(samples['Label'])
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    n_neighbors = min(5, len(X))
    knn = KNeighborsClassifier(n_neighbors=n_neighbors, weights='distance')
    knn.fit(X_scaled, y)
    print(f"KNN model trained with {len(X)} samples")
    return knn, scaler

# ==================== WIFI SOCKET SETUP ====================
def setup_wifi_socket(ip, port):
   
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))
        print(f"WiFi connected to {ip}:{port}")
        return sock
    except Exception as e:
        print(f"WiFi connection error: {e}")
        print("Running without WiFi communication...")
        return None

# ==================== MAIN APPLICATION ====================
class ColorDetectionApp:
    def __init__(self):
        self.cap = None
        self.knn = None
        self.scaler = None
        self.sock = None          
        self.hsv_history = deque(maxlen=HSV_SMOOTHING)
        self.last_prediction_time = 0
        self.last_predicted_color = None
        self.color_to_char = {
            'Green': 'G',
            'Orange': 'O',
            'Pink': 'P',
            'Yellow': 'Y',
            'Unknown': '?'
        }
    
    def initialize(self):
        print(f"Opening camera (index {CAMERA_INDEX})...")
        self.cap = cv2.VideoCapture(CAMERA_INDEX)
        if not self.cap.isOpened():
            print(f"Error: Could not open camera {CAMERA_INDEX}")
            print("Try changing CAMERA_INDEX to 0 (laptop cam) or another number.")
            return False
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        print("Loading dataset and training model...")
        samples = load_dataset_from_csv()
        self.knn, self.scaler = train_knn_model(samples)
        
        if self.knn is None:
            return False
        
        self.sock = setup_wifi_socket(ESP32_IP, ESP32_PORT)
        return True
    
    def extract_hsv_features(self, roi_bgr):
        if roi_bgr.size == 0:
            return [0, 0, 0]
        roi_hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        roi_hsv = cv2.medianBlur(roi_hsv, 3)
        avg_h = np.mean(roi_hsv[:, :, 0])
        avg_s = np.mean(roi_hsv[:, :, 1])
        avg_v = np.mean(roi_hsv[:, :, 2])
        self.hsv_history.append([avg_h, avg_s, avg_v])
        return np.mean(self.hsv_history, axis=0)
    
    def predict_color(self, hsv_values):
        features = np.array([hsv_values])
        features_scaled = self.scaler.transform(features)
        predicted_label = self.knn.predict(features_scaled)[0]
        confidence = np.max(self.knn.predict_proba(features_scaled))
        if confidence < CONFIDENCE_THRESHOLD:
            return "Unknown", confidence
        return predicted_label, confidence
    
    def send_command(self, color_label):
        if self.sock:
            char_code = self.color_to_char.get(color_label, '?')
            try:
                self.sock.sendall(char_code.encode())
                print(f"Sent over WiFi: {char_code}")
            except Exception as e:
                print(f"WiFi send error: {e}")
                self.sock = None
    
    def run(self):
        print("\n" + "="*50)
        print("COLOR DETECTION SYSTEM (WiFi + External Webcam)")
        print("="*50)
        print(f"Camera index: {CAMERA_INDEX}")
        print(f"ESP32 WiFi target: {ESP32_IP}:{ESP32_PORT}")
        print("Controls:")
        print("  'q' - Quit")
        print("  's' - Save current frame")
        print(f"  ROI size: {ROI_SIZE}x{ROI_SIZE} pixels")
        print(f"  Confidence threshold: {CONFIDENCE_THRESHOLD*100}%")
        print("="*50 + "\n")
        
        frame_count = 0
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Error: Failed to capture frame")
                break
            
            frame_count += 1
            height, width = frame.shape[:2]
            center_x, center_y = width // 2, height // 2
            half_size = ROI_SIZE // 2
            
            roi = frame[center_y - half_size:center_y + half_size,
                       center_x - half_size:center_x + half_size]
            
            hsv_values = self.extract_hsv_features(roi)
            
            current_time = time.time()
            if current_time - self.last_prediction_time >= PREDICTION_DELAY:
                predicted_color, confidence = self.predict_color(hsv_values)
                print(f"Frame {frame_count} | HSV: ({int(hsv_values[0]):3d}, {int(hsv_values[1]):3d}, {int(hsv_values[2]):3d}) | "
                      f"Color: {predicted_color} | Confidence: {confidence:.1%}")
                
                self.send_command(predicted_color)
                self.last_predicted_color = predicted_color
                self.last_prediction_time = current_time
            
            # Draw ROI square
            cv2.rectangle(frame, 
                         (center_x - half_size, center_y - half_size),
                         (center_x + half_size, center_y + half_size),
                         (0, 255, 0), 2)
            
            # Display results
            if self.last_predicted_color:
                text_color = (0, 0, 255) if self.last_predicted_color == "Unknown" else (0, 255, 0)
                cv2.rectangle(frame, (10, 10), (320, 100), (0, 0, 0), -1)
                cv2.putText(frame, f"Color: {self.last_predicted_color}", (20, 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)
                cv2.putText(frame, f"HSV: ({int(hsv_values[0])}, {int(hsv_values[1])}, {int(hsv_values[2])})", 
                           (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(frame, f"Conf: {confidence:.0%}", (20, 95),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            
            cv2.putText(frame, "Press 'q' to quit", (width - 150, height - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow('Color Detection System', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                cv2.imwrite(f"capture_{timestamp}.png", frame)
                print(f"Frame saved as capture_{timestamp}.png")
        
        self.cleanup()
    
    def cleanup(self):
        if self.cap:
            self.cap.release()
        if self.sock:
            self.sock.close()
        cv2.destroyAllWindows()
        print("\nSystem shutdown complete")

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    try:
        import cv2
        import sklearn
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("\nPlease install: pip install opencv-python numpy scikit-learn")
        exit(1)
    
    app = ColorDetectionApp()
    if app.initialize():
        app.run()
    else:
        print("Failed to initialize. Check camera index and ESP32 WiFi settings.")

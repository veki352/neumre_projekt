import bpy
import json
import os
import math

# =====================================================
# CLEAN SCENE 
# =====================================================

for obj in bpy.data.objects:
    if obj.type == 'GPENCIL':
        bpy.data.objects.remove(obj, do_unlink=True)


bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)


for gp_data in bpy.data.grease_pencils:
    bpy.data.grease_pencils.remove(gp_data)

# =====================================================
# LOAD JSON
# =====================================================
json_path = r"C:\OpenPose\opoenpose_video10.json"
if not os.path.exists(json_path):
    raise Exception("JSON file not found")

with open(json_path, "r") as f:
    data = json.load(f)

frames = data["frames"]
connections = data["metadata"]["bone_connections"]
has_face = data["metadata"].get("has_face_data", False)

# =====================================================
# FACE DEFINITIONS
# =====================================================
FACE_EYEBROWS_LEFT = ["Face_%d" % i for i in range(17, 22)]  # 17-21: lijeva obrva
FACE_EYEBROWS_RIGHT = ["Face_%d" % i for i in range(22, 27)]  # 22-26: desna obrva
FACE_NOSE = ["Face_nose_%d" % i for i in range(9)]  # 0-8: nos

# =====================================================
# CREATE SINGLE GREASE PENCIL OBJECT
# =====================================================

bpy.ops.object.gpencil_add(type='EMPTY')
gp = bpy.context.object
gp.name = "Stickman_Animation"


while len(gp.data.layers) > 0:
    gp.data.layers.remove(gp.data.layers[0])

# Stvori različite slojeve za različite dijelove tijela
body_layer = gp.data.layers.new("Body", set_active=True)
head_layer = gp.data.layers.new("Head", set_active=False)  
face_eyes_layer = gp.data.layers.new("Face_Eyes", set_active=False)
face_eyebrows_layer = gp.data.layers.new("Face_Eyebrows", set_active=False)
face_nose_layer = gp.data.layers.new("Face_Nose", set_active=False)
ears_layer = gp.data.layers.new("Ears", set_active=False)  


body_layer.color = (1.0, 0.5, 0.0)  
head_layer.color = (1.0, 1.0, 1.0) 
face_eyes_layer.color = (0.0, 0.8, 1.0)  
face_eyebrows_layer.color = (0.6, 0.4, 0.2)  
face_nose_layer.color = (1.0, 0.0, 0.0) 
ears_layer.color = (1.0, 1.0, 1.0)  

# Postavi debljinu linija za svaki sloj (integer vrijednosti)
body_layer.line_change = 2
head_layer.line_change = 2  # Debljina linije glave
face_eyes_layer.line_change = 1
face_eyebrows_layer.line_change = 1
face_nose_layer.line_change = 1
ears_layer.line_change = 1

# =====================================================
# TIMELINE
# =====================================================
bpy.context.scene.render.fps = data["metadata"].get("fps", 30)
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = len(frames)

# =====================================================
# POMOĆNE FUNKCIJE ZA CRTANJE
# =====================================================
def draw_circle(frame, center_x, center_y, radius=0.01, segments=16, line_width=3):
    """Crtaj krug oko zadane točke"""
    stroke = frame.strokes.new()
    stroke.line_width = line_width
    stroke.points.add(segments)
    
    for i in range(segments):
        angle = (2 * math.pi * i) / segments
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        stroke.points[i].co = (x, y, 0)
        stroke.points[i].pressure = 1.0
    
    return stroke

def draw_line_between_points(frame, point1, point2, line_width=5):
    """Crtaj liniju između dvije točke"""
    stroke = frame.strokes.new()
    stroke.line_width = line_width
    stroke.points.add(2)
    stroke.points[0].co = point1
    stroke.points[1].co = point2
    stroke.points[0].pressure = 1.0
    stroke.points[1].pressure = 1.0
    
    return stroke

def draw_connected_points(frame, points_list, close_loop=False, line_width=4):
    """Crtaj linije između povezanih točaka"""
    if len(points_list) < 2:
        return
    
    for i in range(len(points_list) - 1):
        draw_line_between_points(frame, points_list[i], points_list[i + 1], line_width)
    
    if close_loop and len(points_list) >= 3:
        draw_line_between_points(frame, points_list[-1], points_list[0], line_width)

def get_or_create_frame(layer, frame_number):
    """Dohvati frame, ili stvori novi ako ne postoji."""
    # Provjeri postoji li već frame s tim brojem
    for existing_frame in layer.frames:
        if existing_frame.frame_number == frame_number:
            # Obriši sve strokeove u postojećem frameu
            existing_frame.strokes.clear()
            return existing_frame
    
    
    return layer.frames.new(frame_number)

# =====================================================
# FUNKCIJA ZA CRTANJE VRATA (U BODY_LAYER)
# =====================================================
def draw_neck(frame_data, body_frame):
    """Crtaj vrat u body_layer"""
    kp = frame_data["keypoints"]
    
    # Crtaj vrat (spoj između glave i vrata)
    if "Head" in kp and "Neck" in kp:
        head = kp["Head"]
        neck = kp["Neck"]
        
        if head["confidence"] > 0.1 and neck["confidence"] > 0.1:
            # Crtaj vrat od vrata do glave
            head_x, head_y = head["x"], head["y"]
            neck_x, neck_y = neck["x"], neck["y"]
            
            # Crtaj vrat (50% duljine)
            mid_x = neck_x + (head_x - neck_x) * 0.5
            mid_y = neck_y + (head_y - neck_y) * 0.5
            
            draw_line_between_points(body_frame, 
                                    (neck_x, neck_y, 0), 
                                    (mid_x, mid_y, 0), 
                                    line_width=8)

# =====================================================
# FUNKCIJA ZA CRTANJE GLAVE
# =====================================================
def draw_head(frame_data, head_frame):
    """Crtaj glavu kao proporcionalni krug"""
    kp = frame_data["keypoints"]
    
    # Ako imamo Head točku, koristimo je kao centar glave
    if "Head" in kp and kp["Head"]["confidence"] > 0.1:
        head_x = kp["Head"]["x"]
        head_y = kp["Head"]["y"]
        
        # JAKO MALA glava - početna vrijednost
        head_radius = 0.075  
        
        # Ako imamo oči, možemo prilagoditi veličinu glave
        if "REye" in kp and "LEye" in kp:
            if kp["REye"]["confidence"] > 0.1 and kp["LEye"]["confidence"] > 0.1:
                reye_x, reye_y = kp["REye"]["x"], kp["REye"]["y"]
                leye_x, leye_y = kp["LEye"]["x"], kp["LEye"]["y"]
                
                # Izračunaj udaljenost između očiju
                eye_distance = math.sqrt((reye_x - leye_x)**2 + (reye_y - leye_y)**2)
                
                # Glava treba biti proporcionalna udaljenosti između očiju
                head_radius = eye_distance * 1.2  # Glava je 20% veća od udaljenosti između očiju
        
        # OGRANIČI maksimalnu veličinu glave
        head_radius = min(head_radius, 0.075)  # Maksimalno 0.025
        
        # Nacrtaj glavu kao krug
        draw_circle(head_frame, head_x, head_y, radius=head_radius, 
                    segments=20, line_width=5)
        
        return True
    
    return False

# =====================================================
# FUNKCIJA ZA CRTANJE DETALJA LICA
# =====================================================
def draw_face_features(frame_data, head_frame, face_eyes_frame, 
                       face_eyebrows_frame, face_nose_frame, ears_frame):
    """Crtaj detalje lica unutar glave"""
    kp = frame_data["keypoints"]
    
    # --- CRTANJE OČIJU ---
    if "REye" in kp and kp["REye"]["confidence"] > 0.1:
        reye_x = kp["REye"]["x"]
        reye_y = kp["REye"]["y"]
        draw_circle(face_eyes_frame, reye_x, reye_y, radius=0.004, line_width=2)
    
    if "LEye" in kp and kp["LEye"]["confidence"] > 0.1:
        leye_x = kp["LEye"]["x"]
        leye_y = kp["LEye"]["y"]
        draw_circle(face_eyes_frame, leye_x, leye_y, radius=0.004, line_width=2)
    
    # --- CRTANJE UŠIJU (NA GLAVI, BLIŽE GLAVI) ---
    head_x = head_y = None
    head_radius = 0.075
    
    if "Head" in kp and kp["Head"]["confidence"] > 0.1:
        head_x = kp["Head"]["x"]
        head_y = kp["Head"]["y"]
        
        # Izračunaj radijus glave
        if "REye" in kp and "LEye" in kp:
            if kp["REye"]["confidence"] > 0.1 and kp["LEye"]["confidence"] > 0.1:
                reye_x, reye_y = kp["REye"]["x"], kp["REye"]["y"]
                leye_x, leye_y = kp["LEye"]["x"], kp["LEye"]["y"]
                eye_distance = math.sqrt((reye_x - leye_x)**2 + (reye_y - leye_y)**2)
                head_radius = min(eye_distance * 1.2, 0.075)
    
    # Desno uho - na desnoj strani glave
    if "REar" in kp and kp["REar"]["confidence"] > 0.1 and head_x is not None and head_y is not None:
        # Prvo uzmi originalnu poziciju uha iz JSON-a
        ear_x = kp["REar"]["x"]
        ear_y = kp["REar"]["y"]
        
        # Izračunaj smjer od centra glave prema uhu
        dx = ear_x - head_x
        dy = ear_y - head_y
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Ako je uho unutar glave, pomakni ga na rub glave - SAMO 5% IZVAN
        if distance > 0 and distance < head_radius * 1.5:  # Ako je unutar 1.5x radijusa glave
            # Normaliziraj vektor
            dx /= distance
            dy /= distance
            
            # Postavi uho na rub glave (SAMO 5% IZVAN ruba glave)
            ear_x = head_x + dx * (head_radius * 1.05)  
            ear_y = head_y + dy * (head_radius * 1.05)
        else:
            
            if distance > head_radius * 1.1:  
                dx /= distance
                dy /= distance
                ear_x = head_x + dx * (head_radius * 1.05)  
                ear_y = head_y + dy * (head_radius * 1.05)
        
        # Nacrtaj uho kao polukrug koji se naliježe na glavu
        # Napravimo polukrug na vanjskoj strani glave
        ear_radius = head_radius * 0.25  # Uho je 25% veličine glave (manje nego prije)
        
        # Odredimo kut uha u odnosu na centar glave
        angle = math.atan2(dy, dx)
        
        # Nacrtaj polukrug (180 stupnjeva)
        stroke = ears_frame.strokes.new()
        stroke.line_width = 3  # Tanja linija za uho
        segments = 12
        
        # Crtamo samo vanjsku polovicu kruga
        start_angle = angle - math.pi/2  # 90 stupnjeva lijevo od smjera
        end_angle = angle + math.pi/2    # 90 stupnjeva desno od smjera
        
        stroke.points.add(segments)
        for i in range(segments):
            t = i / (segments - 1)
            current_angle = start_angle + t * (end_angle - start_angle)
            
            x = ear_x + ear_radius * math.cos(current_angle)
            y = ear_y + ear_radius * math.sin(current_angle)
            stroke.points[i].co = (x, y, 0)
            stroke.points[i].pressure = 1.0
    
    # Lijevo uho - na lijevoj strani glave
    if "LEar" in kp and kp["LEar"]["confidence"] > 0.1 and head_x is not None and head_y is not None:
        # Prvo uzmi originalnu poziciju uha iz JSON-a
        ear_x = kp["LEar"]["x"]
        ear_y = kp["LEar"]["y"]
        
        # Izračunaj smjer od centra glave prema uhu
        dx = ear_x - head_x
        dy = ear_y - head_y
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Ako je uho unutar glave, pomakni ga na rub glave - SAMO 5% IZVAN
        if distance > 0 and distance < head_radius * 1.5:  # Ako je unutar 1.5x radijusa glave
            # Normaliziraj vektor
            dx /= distance
            dy /= distance
            
            # Postavi uho na rub glave (SAMO 5% IZVAN ruba glave)
            ear_x = head_x + dx * (head_radius * 1.05)  
            ear_y = head_y + dy * (head_radius * 1.05)
        else:
            
            if distance > head_radius * 1.1:  
                dx /= distance
                dy /= distance
                ear_x = head_x + dx * (head_radius * 1.05)  
                ear_y = head_y + dy * (head_radius * 1.05)
        
        # Nacrtaj uho kao polukrug koji se naliježe na glavu
        ear_radius = head_radius * 0.25  
        
        # Odredimo kut uha u odnosu na centar glave
        angle = math.atan2(dy, dx)
        
        # Nacrtaj polukrug (180 stupnjeva)
        stroke = ears_frame.strokes.new()
        stroke.line_width = 3  # Tanja linija za uho
        segments = 12
        
        # Crtamo samo vanjsku polovicu kruga
        start_angle = angle - math.pi/2  # 90 stupnjeva lijevo od smjera
        end_angle = angle + math.pi/2    # 90 stupnjeva desno od smjera
        
        stroke.points.add(segments)
        for i in range(segments):
            t = i / (segments - 1)
            current_angle = start_angle + t * (end_angle - start_angle)
            
            x = ear_x + ear_radius * math.cos(current_angle)
            y = ear_y + ear_radius * math.sin(current_angle)
            stroke.points[i].co = (x, y, 0)
            stroke.points[i].pressure = 1.0
    
    # --- CRTANJE OBREVA ---
    if has_face:
        # Lijeva obrva
        left_eyebrow_points = []
        for face_id in FACE_EYEBROWS_LEFT:
            if face_id in kp and kp[face_id]["confidence"] > 0.15:
                x = kp[face_id]["x"]
                y = kp[face_id]["y"]
                left_eyebrow_points.append((x, y, 0))
        
        if len(left_eyebrow_points) >= 2:
            draw_connected_points(face_eyebrows_frame, left_eyebrow_points, close_loop=False, line_width=1)
    
        # Desna obrva
        right_eyebrow_points = []
        for face_id in FACE_EYEBROWS_RIGHT:
            if face_id in kp and kp[face_id]["confidence"] > 0.15:
                x = kp[face_id]["x"]
                y = kp[face_id]["y"]
                right_eyebrow_points.append((x, y, 0))
        
        if len(right_eyebrow_points) >= 2:
            draw_connected_points(face_eyebrows_frame, right_eyebrow_points, close_loop=False, line_width=1)
        
        # --- CRTANJE NOSA ---
        nose_points = []
        for face_id in FACE_NOSE:
            if face_id in kp and kp[face_id]["confidence"] > 0.15:
                x = kp[face_id]["x"]
                y = kp[face_id]["y"]
                nose_points.append((x, y, 0))
        
        if len(nose_points) >= 2:
            # Nacrtaj linije između točaka nosa
            for i in range(len(nose_points) - 1):
                draw_line_between_points(face_nose_frame, nose_points[i], nose_points[i + 1], line_width=1)
            
            # Spoji prvu i zadnju točku ako ima dovoljno točaka
            if len(nose_points) >= 3:
                draw_line_between_points(face_nose_frame, nose_points[0], nose_points[-1], line_width=1)

# =====================================================
# FUNKCIJA ZA CRTANJE TIJELA (BEZ GLAVE I BEZ KRUŽIĆA)
# =====================================================
def draw_body_only(frame_data, body_frame):
    """Crtaj samo tijelo stickmana (bez glave, lica i kružića)"""
    kp = frame_data["keypoints"]
    
    # Lista veza koje su DIO TIJELA (bez glave i lica)
    body_connections = [
        ("Neck", "RShoulder"),
        ("Neck", "LShoulder"),
        ("RShoulder", "RElbow"),
        ("RElbow", "RWrist"),
        ("LShoulder", "LElbow"),
        ("LElbow", "LWrist"),
        ("Neck", "MidHip"),
        ("MidHip", "RHip"),
        ("MidHip", "LHip"),
        ("RHip", "RKnee"),
        ("RKnee", "RAnkle"),
        ("LHip", "LKnee"),
        ("LKnee", "LAnkle")
    ]
    
    # Crtaj sve veze tijela
    for a, b in body_connections:
        if a not in kp or b not in kp:
            continue

        pa = kp[a]
        pb = kp[b]

        if pa["confidence"] < 0.1 or pb["confidence"] < 0.1:
            continue

        # Debljine linija za različite dijelove tijela
        line_width = 4
        if "Shoulder" in a or "Shoulder" in b:
            line_width = 5
        elif "Hip" in a or "Hip" in b:
            line_width = 6
        elif "Knee" in a or "Knee" in b:
            line_width = 4
        elif "Ankle" in a or "Ankle" in b:
            line_width = 3
        elif "Wrist" in a or "Wrist" in b:
            line_width = 2
        elif "Elbow" in a or "Elbow" in b:
            line_width = 3
        
        draw_line_between_points(body_frame, 
                                (pa["x"], pa["y"], 0), 
                                (pb["x"], pb["y"], 0), 
                                line_width=line_width)

# =====================================================
# GLAVNA PETLJA ZA CRTANJE STICKMANA
# =====================================================
print("Drawing stickman animation...")

for i, frame_data in enumerate(frames):
    frame_number = i + 1
    bpy.context.scene.frame_set(frame_number)
    
    # Stvori frameove za sve slojeve (brišući postojeće strokeove)
    body_frame = get_or_create_frame(body_layer, frame_number)
    head_frame = get_or_create_frame(head_layer, frame_number)
    face_eyes_frame = get_or_create_frame(face_eyes_layer, frame_number)
    face_eyebrows_frame = get_or_create_frame(face_eyebrows_layer, frame_number)
    face_nose_frame = get_or_create_frame(face_nose_layer, frame_number)
    ears_frame = get_or_create_frame(ears_layer, frame_number)
    
    # --- CRTANJE TIJELA 
    draw_body_only(frame_data, body_frame)
    
    # --- CRTANJE VRATA (U BODY_LAYER) ---
    draw_neck(frame_data, body_frame)
    
    # --- CRTANJE GLAVE ---
    draw_head(frame_data, head_frame)
    
    # --- CRTANJE DETALJA LICA ---
    draw_face_features(frame_data, head_frame, face_eyes_frame,
                      face_eyebrows_frame, face_nose_frame, ears_frame)
    
    if frame_number % 25 == 0:
        print(f"Processed frame {frame_number}/{len(frames)}")

print("✅ Stickman animation complete")

# =====================================================
# CAMERA SETUP
# =====================================================
bpy.ops.object.camera_add(location=(0, 0, 10))  # Blíže za bolji prikaz
cam = bpy.context.object
cam.name = "Animation_Camera"
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 1.5  # Manji scale za bolji prikaz
bpy.context.scene.camera = cam

# Postavi poziciju kamere
cam.location = (0, 0, 10)
cam.rotation_euler = (0, 0, 0)

# =====================================================
# LIGHT SETUP
# =====================================================
# Dodaj svjetlo
bpy.ops.object.light_add(type='SUN', location=(10, 10, 20))
light = bpy.context.object
light.data.energy = 2.0

# =====================================================
# RENDER SETTINGS
# =====================================================
bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.render.film_transparent = True

# Postavi pozadinsku boju na crnu za bolji kontrast
bpy.context.scene.world.color = (0, 0, 0)

# =====================================================
# OUTPUT INFO
# =====================================================
print("\n" + "="*50)
print("🎬 STICKMAN ANIMATION READY")
print("="*50)
print("Layers created:")
print("  • Body - Orange (tijelo + vrat)")
print("  • Head - White (mala glava)")
print("  • Face_Eyes - Blue (oči)")
print("  • Face_Eyebrows - Brown (obrve)")
print("  • Face_Nose - Red (nos)")
print("  • Ears - White (uši na glavi)")
print("\nControls:")
print("  • ALT+A - Play animation")
print("  • N - Toggle sidebar (to see layers)")
print("  • Space - Play/Pause")
print("="*50)
print("\n💡 Promjene:")
print("   - Uši su sada samo 5% izvan ruba glave (umjesto 20%)")
print("   - Uši su manje (25% veličine glave umjesto 40%)")
print("   - Ako su uši već izvan glave, povlače se na 5% izvan ruba")
print("   - Uši su bliže glavi i izgledaju prirodnije")
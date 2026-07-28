from django.shortcuts import render
from django.template import RequestContext
from django.http import HttpResponse
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import connection
import datetime
import re
import os
from pathlib import Path



def ensure_table_exists():
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rating (
                customer_name VARCHAR(50),
                rating DOUBLE PRECISION,
                facial_expression VARCHAR(50),
                photo_path VARCHAR(255),
                rating_date VARCHAR(50)
            )
        """)


def Index(request):
    if request.method == 'GET':
        return render(request, 'index.html', {})


def User(request):
    if request.method == 'GET':
        return render(request, 'User.html', {})


def Admin(request):
    if request.method == 'GET':
        return render(request, 'Admin.html', {})


def AdminLogin(request):
    if request.method == 'POST':
        username = request.POST.get('t1', False)
        password = request.POST.get('t2', False)
        if username == 'admin' and password == 'admin':
            context = {'data': 'welcome ' + username}
            return render(request, 'AdminScreen.html', context)
        else:
            context = {'data': 'login failed'}
            return render(request, 'Admin.html', context)


def ViewRating(request):
    if request.method == 'GET':
        ensure_table_exists()
        strdata = '<table border=1 align=center width=100%><tr><th>Customer Name</th><th>Rating</th><th>Facial Expression</th><th>Photo</th> <th>Date & Time</th></tr><tr>'
        with connection.cursor() as cursor:
            cursor.execute("SELECT customer_name, rating, facial_expression, photo_path, rating_date FROM rating")
            rows = cursor.fetchall()
            for row in rows:
                strdata += f'<td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td><img src="/static/photo/{row[0]}.png" width=200 height=200></img></td><td>{row[4]}</td></tr>'
        context = {'data': strdata}
        return render(request, 'ViewRatings.html', context)


def Rating(request):
    if request.method == 'POST' and request.FILES.get('t3'):
        try:
            output = 'Neutral'
            myfile = request.FILES['t3']
            name = request.POST.get('t1', 'Unknown')
            rating = request.POST.get('t2', '0')

            # Sanitize file name
            name_sanitized = re.sub(r'[^\w\-]', '_', name)

            # Save file inside static/photo directory
            photo_dir = os.path.join(settings.BASE_DIR, 'FacialApp', 'static', 'photo')
            os.makedirs(photo_dir, exist_ok=True)
            
            photo_filename = name_sanitized + '.png'
            photo_full_path = os.path.join(photo_dir, photo_filename)

            with open(photo_full_path, 'wb+') as destination:
                for chunk in myfile.chunks():
                    destination.write(chunk)

            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Get current directory and build paths to models
            current_dir = Path(__file__).resolve().parent

            # Build relative paths to the models
            detection_model_path = current_dir / 'haarcascade_frontalface_default.xml'
            emotion_model_path = current_dir / '_mini_XCEPTION.106-0.65.hdf5'

            # Check if model files exist
            if not detection_model_path.exists():
                raise FileNotFoundError(f"File not found: {detection_model_path}")
            if not emotion_model_path.exists():
                raise FileNotFoundError(f"File not found: {emotion_model_path}")

            # Import ML dependencies lazily
            import cv2
            import numpy as np
            from keras.models import load_model
            from keras.preprocessing.image import img_to_array

            # Load models
            face_detection = cv2.CascadeClassifier(str(detection_model_path))
            emotion_classifier = load_model(str(emotion_model_path), compile=False)
            EMOTIONS = ["angry", "disgust", "scared", "happy", "sad", "surprised", "neutral"]


            # Load and preprocess image
            frame = cv2.imread(photo_full_path)
            if frame is not None:
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_detection.detectMultiScale(
                    gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE
                )
                print("Faces detected:", len(faces))

                if len(faces) > 0:
                    (fX, fY, fW, fH) = sorted(faces, reverse=True, key=lambda x: (x[2] - x[0]) * (x[3] - x[1]))[0]
                    roi = gray_frame[fY:fY + fH, fX:fX + fW]
                    roi = cv2.resize(roi, (48, 48))
                    roi = roi.astype("float") / 255.0
                    roi = img_to_array(roi)
                    roi = np.expand_dims(roi, axis=0)

                    # Predict emotion
                    preds = emotion_classifier.predict(roi)[0]
                    label = EMOTIONS[preds.argmax()]
                    print("Detected Emotion:", label)

                    if label == 'happy':
                        output = 'Satisfied'
                    elif label == 'neutral':
                        output = 'Neutral'
                    else:
                        output = 'Disappointed'

            # Insert into DB using Django connection
            ensure_table_exists()
            with connection.cursor() as cursor:
                query = """INSERT INTO rating (customer_name, rating, facial_expression, photo_path, rating_date)
                           VALUES (%s, %s, %s, %s, %s)"""
                cursor.execute(query, (name, rating, output, photo_filename, current_time))

            context = {'data': f'Your Rating is : {rating} and Facial Expression : {output}'}

        except Exception as e:
            print("Error:", str(e))
            context = {'data': f'Error in request process: {str(e)}'}

        return render(request, 'User.html', context)
    else:
        return render(request, 'User.html', {'data': 'Invalid request: No file uploaded.'})


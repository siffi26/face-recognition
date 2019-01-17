from keras import backend as K
import time
from multiprocessing.dummy import Pool
import cv2
import os
import glob
import numpy as np
from numpy import genfromtxt
import tensorflow as tf
from fr_utils import *
from inception_blocks_v2 import *
import imageio
from keras.models import load_model
import os

K.set_image_data_format('channels_first')
PADDING = 50
ready_to_detect_identity = True

def triplet_loss(y_true, y_pred, alpha = 0.3):
    """
    Calculate the triplet_loss to find the difference between two images
    """
    anchor, positive, negative = y_pred[0], y_pred[1], y_pred[2]

    pos_dist = tf.reduce_sum(tf.square(tf.subtract(anchor, positive)), axis=-1)
    neg_dist = tf.reduce_sum(tf.square(tf.subtract(anchor, negative)), axis=-1)
    basic_loss = tf.add(tf.subtract(pos_dist, neg_dist), alpha)
    loss = tf.reduce_sum(tf.maximum(basic_loss, 0.0))

    return loss

def load_face_recognition_model():
    if os.path.isfile('models/frmodel.h5'):
        print('Model is present')
        model = load_model('models/frmodel.h5', custom_objects = {'triplet_loss': triplet_loss})
    else:
        model = faceRecoModel(input_shape = (3, 96, 96))
        model.compile(optimizer = 'adam', loss = triplet_loss, metrics = ['accuracy'])
        load_weights_from_FaceNet(model)
        model.save('models/frmodel.h5')
    return model

FRmodel = load_face_recognition_model()
face_cascade = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')

def prepare_database():
    database = {}
    # load all the images of individuals to recognize into the database
    for file in glob.glob("database/*"):
        identity = os.path.splitext(os.path.basename(file))[0]
        image = imageio.imread(file)
        
        (x1, y1, x2, y2) = extract_faces(image, face_cascade)[0]
        height, width, channels = image.shape
        face_image = image[max(0, y1):min(height, y2), max(0, x1):min(width, x2)]
        
        database[identity] = img_to_encoding(face_image, FRmodel)
    return database

def recognize_still_image(image):
    image = process_frame(image, image, face_cascade)   
    return image

def show_image(image, identity):
    cv2.imshow(identity, image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def extract_faces(image, face_cascade):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    all_faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    face_coordinates = []
    
    for (x, y, w, h) in all_faces:
        x1 = x - PADDING
        y1 = y - PADDING
        x2 = x + w + PADDING
        y2 = y + h + PADDING
        face_coordinates.append([x1, y1, x2, y2])
    return face_coordinates

def process_frame(img, frame, face_cascade):
    """
    Determine whether the current frame contains the faces of people from our database
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    # Loop through all the faces detected and determine whether or not they are in the database
    identities = []
    for (x1, y1, x2, y2) in extract_faces(image, face_cascade):
        
        identity = find_identity(frame, x1, y1, x2, y2)
        # print(identity)

        if identity is not None:
            img = cv2.rectangle(frame, (x1, y1), (x2, y2), (255,0,0), 2)
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(img, identity,(x1, y1), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
            identities.append(identity)

    return img

def find_identity(frame, x1, y1, x2, y2):
    """
    Determine whether the face contained within the bounding box exists in our database
    """
    height, width, channels = frame.shape
    # The padding is necessary since the OpenCV face detector creates the bounding box around the face and not the head
    part_image = frame[max(0, y1):min(height, y2), max(0, x1):min(width, x2)]
    
    return who_is_it(part_image, database, FRmodel)

def who_is_it(image, database, model):
    """
    Implements face recognition for the happy house by finding who is the person on the image_path image.
    """
    encoding = img_to_encoding(image, model)
    min_dist = 100
    identity = None
    
    # Loop over the database dictionary's names and encodings.
    for (name, db_enc) in database.items():
        # Compute L2 distance between the target "encoding" and the current "emb" from the database.
        dist = np.linalg.norm(db_enc - encoding)
        print('distance for %s is %s' %(name, dist))
        # If this distance is less than the min_dist, then set min_dist to dist, and identity to name
        if dist < min_dist:
            min_dist = dist
            identity = name
    
    if min_dist > 0.7:
        return None
    else:
        return str(identity)

if __name__ == "__main__":
    database = prepare_database()
    image_list = glob.glob('input/*')
    print(image_list)
    for (i, image_name) in enumerate(image_list):
        image = imageio.imread(image_name)
        output = recognize_still_image(image)
        imageio.imwrite('output/' + str(i) + '.jpg', output)

# ### References:
# 
# - Florian Schroff, Dmitry Kalenichenko, James Philbin (2015). [FaceNet: A Unified Embedding for Face Recognition and Clustering](https://arxiv.org/pdf/1503.03832.pdf)
# - Yaniv Taigman, Ming Yang, Marc'Aurelio Ranzato, Lior Wolf (2014). [DeepFace: Closing the gap to human-level performance in face verification](https://research.fb.com/wp-content/uploads/2016/11/deepface-closing-the-gap-to-human-level-performance-in-face-verification.pdf) 
# - The pretrained model we use is inspired by Victor Sy Wang's implementation and was loaded using his code: https://github.com/iwantooxxoox/Keras-OpenFace.
# - Our implementation also took a lot of inspiration from the official FaceNet github repository: https://github.com/davidsandberg/facenet 
# 

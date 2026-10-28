#EXPLANATION IN NOTION SUBWAY SURFERS
import cv2
import mediapipe as mp

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
 #mp_pose contains the pose detection model 33 landmarks
 #mp_drawing contains the model to draw the landmarks and connections

og_image=cv2.imread("images/person1.png")
image=og_image.copy()

if image is None:
    raise FileNotFoundError("Image not found. Put person.jpg inside images/")

#with the help of mp_pose we detect the landmarks and with #mp_drawning we draw the landmarks and connections
with mp_pose.Pose(static_image_mode=True) as pose:
    image_rgb=cv2.cvtColor(image, cv2.COLOR_BGR2RGB) #opencv2 gives bgr but mediapipe needs rgb
    results=pose.process(image_rgb) #results contain the ladmarks

    if results.pose_landmarks:
        # 👇 ADD THIS LINE HERE
        print(len(results.pose_landmarks.landmark))

    if results.pose_landmarks:
        mp_drawing.draw_landmarks(
            image,
            results.pose_landmarks,
            mp_pose.POSE_CONNECTIONS
        )

cv2.imshow("Pose Detection image", image)
cv2.imshow("Normal image",og_image)
cv2.waitKey(0)
cv2.destroyAllWindows()
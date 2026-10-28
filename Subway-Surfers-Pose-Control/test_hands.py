import cv2
from pose_utils import detectPose
from gesture_utils import checkHandsJoined

cam=cv2.VideoCapture(0)

while cam.isOpened():
    ret, frame=cam.read()
    if not ret:
        break

    frame=cv2.flip(frame,1) #With flipping: Movement feels natural, like looking into a mirror. else left hand appears as right hand 1- horizontal flip
    frame,results=detectPose(frame)

    if results.pose_landmarks:
        frame,status= checkHandsJoined(frame,results, draw=True)

    cv2.imshow("Hands Joined Test", frame)

    if cv2.waitKey(1) & 0xFF==27:
        break

cam.release()
cv2.destroyAllWindows()
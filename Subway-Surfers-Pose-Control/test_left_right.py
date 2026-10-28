import cv2
from pose_utils import detectPose
from gesture_utils import checkLeftRight

cam = cv2.VideoCapture(0)

while cam.isOpened():
    ret, frame = cam.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    frame, results = detectPose(frame)

    if results.pose_landmarks:
        frame, position = checkLeftRight(frame, results, draw=True)

    cv2.imshow("Left Right Test", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cam.release()
cv2.destroyAllWindows()



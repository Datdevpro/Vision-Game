import cv2
import pyautogui
from pose_utils import detectPose
from gesture_utils import checkJumpCrouch

cam = cv2.VideoCapture(0)
MID_Y = None
y_pos_index = 1  # 0=crouch, 1=stand, 2=jump

while cam.isOpened():
    ret, frame = cam.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    frame, results = detectPose(frame)

    if results.pose_landmarks:
        if MID_Y is None:
            left = results.pose_landmarks.landmark[11]
            right = results.pose_landmarks.landmark[12]
            MID_Y = int(((left.y + right.y) / 2) * frame.shape[0])

        frame, posture = checkJumpCrouch(frame, results, MID_Y, draw=True)

        if posture == "Jumping" and y_pos_index == 1:
            pyautogui.press('up')
            y_pos_index = 2

        elif posture == "Crouching" and y_pos_index == 1:
            pyautogui.press('down')
            y_pos_index = 0

        elif posture == "Standing":
            y_pos_index = 1

    cv2.imshow("Jump Crouch Key Test", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cam.release()
cv2.destroyAllWindows()

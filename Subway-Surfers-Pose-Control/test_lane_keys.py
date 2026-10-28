import cv2
import pyautogui
from pose_utils import detectPose
from gesture_utils import checkLeftRight

cam = cv2.VideoCapture(0)
x_pos_index = 1  # start at center

while cam.isOpened():
    ret, frame = cam.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    frame, results = detectPose(frame)

    if results.pose_landmarks:
        frame, position = checkLeftRight(frame, results, draw=True)

        if position == "Left" and x_pos_index != 0:
            pyautogui.press('left')
            x_pos_index -= 1

        elif position == "Right" and x_pos_index != 2:
            pyautogui.press('right')
            x_pos_index += 1

        elif position == "Center":
            x_pos_index = 1

    cv2.imshow("Lane Control Test", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cam.release()
cv2.destroyAllWindows()

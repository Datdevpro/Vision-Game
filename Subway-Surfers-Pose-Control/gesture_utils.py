import cv2
from math import hypot

# MediaPipe's 33-point pose landmark indices (shared by Solutions and Tasks).
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_WRIST = 15
RIGHT_WRIST = 16

def checkHandsJoined(image,results,draw=False):
    height,width,_=image.shape
    output_image=image.copy()

    left_wrist=results.pose_landmarks.landmark[LEFT_WRIST]
    right_wrist=results.pose_landmarks.landmark[RIGHT_WRIST]

    left=(int(left_wrist.x*width),int(left_wrist.y*height))
    right=(int(right_wrist.x*width),int(right_wrist.y*height))

    distance=int(hypot(left[0]-right[0],left[1]-right[1]))

    if distance<130:
        status="Hands Joined"
        color=(0,255,0)
    else:
        status="Hands Not Joined"
        color=(0,0,255)

    if draw:
        cv2.putText(output_image, status, (10,30), cv2.FONT_HERSHEY_PLAIN,2,color,3)
        cv2.putText(output_image, f"Distance:{distance}", (10,60), cv2.FONT_HERSHEY_PLAIN,2,color,3)

    return output_image,status


def checkLeftRight(image, results, draw=False):
    height, width, _ = image.shape
    output_image = image.copy()

    # Shoulder landmarks
    left_shoulder = results.pose_landmarks.landmark[LEFT_SHOULDER]
    right_shoulder = results.pose_landmarks.landmark[RIGHT_SHOULDER]

    left_x = int(left_shoulder.x * width)
    right_x = int(right_shoulder.x * width)

    center_x = width // 2


    if left_x < center_x and right_x < center_x:
        position = "Left"
    elif left_x > center_x and right_x > center_x:
        position = "Right"
    else:
        position = "Center"

    if draw:
        cv2.putText(output_image, f"Position: {position}", (10, height - 20),
                    cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 3)
        cv2.line(output_image, (center_x, 0), (center_x, height), (255, 255, 255), 2)

    return output_image, position


def checkJumpCrouch(image, results, MID_Y, draw=False):
    height, width, _ = image.shape
    output_image = image.copy()

    left_shoulder = results.pose_landmarks.landmark[LEFT_SHOULDER]
    right_shoulder = results.pose_landmarks.landmark[RIGHT_SHOULDER]

    left_y = int(left_shoulder.y * height)
    right_y = int(right_shoulder.y * height)

    actual_mid_y = (left_y + right_y) // 2

    lower_bound = MID_Y - 60
    upper_bound = MID_Y + 100

    if actual_mid_y < lower_bound:
        posture = "Jumping"
    elif actual_mid_y > upper_bound:
        posture = "Crouching"
    else:
        posture = "Standing"

    if draw:
        cv2.putText(output_image, posture, (10, height - 60),
                    cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 3)
        cv2.line(output_image, (0, MID_Y), (width, MID_Y), (255, 255, 255), 2)

    return output_image, posture

import cv2
import time
import pyautogui

from pose_utils import detectPose
from gesture_utils import (
    checkHandsJoined,
    checkLeftRight,
    checkJumpCrouch
)

#Opne Webcam
camera=cv2.VideoCapture(0)
camera.set(3,1280)
camera.set(4,960)

cv2.namedWindow("Subway Surfers with Pose Control",cv2.WINDOW_NORMAL)

#Game state Variables
game_started=False
x_pos_index=1 #0=left, 1=Center, 2=right
y_pos_index=1 #0=crouch 1=stand and 2=jump

last_jump_time = 0
JUMP_COOLDOWN = 0.7  # seconds


#makes key presses human-like
pyautogui.PAUSE = 0.15
pyautogui.FAILSAFE = True

#BROWSER_X = 1200   # CHANGE THIS
#BROWSER_Y = 600    # CHANGE THIS

MID_Y=None
counter=0
NUM_FRAMES=10
prev_time=0 #for calculating fps

while camera.isOpened():
    ret, frame=camera.read()
    if not ret:
        break

    frame=cv2.flip(frame,1)
    frame_height, frame_width, _=frame.shape

    frame,results=detectPose(frame, draw=game_started)

    if results.pose_landmarks:
        #------- GAME START -------------
        if not game_started:
            cv2.putText(frame, "Join Hands to Start",(10,frame_height-20),cv2.FONT_HERSHEY_PLAIN,2,(0,255,0),3)
        frame, hand_status=checkHandsJoined(frame,results,draw=True)

            #if hands joined, game_started=true, calculate the MID_Y and click to start the game
        if hand_status=="Hands Joined":
            counter+=1 #keep detected atleast for 10 fps
            if counter==NUM_FRAMES:
                if not game_started:
                    game_started=True

                    #Calibrate MID_Y
                    left=results.pose_landmarks.landmark[11] #left shoulder
                    right=results.pose_landmarks.landmark[12] # right shoulder
                    MID_Y=int(((left.y+right.y)/2)*frame_height)

                    #click to start the game in the browser
                    pyautogui.click(x=frame_width//2, y=frame_height//2)
                    time.sleep(0.3)  # allow focus to switch

                else:
                    pyautogui.press('space')

                counter=0
        else:
            counter=0

        #-----GAME CONTROLS-----

        if game_started:

            #LEFT AND RIGHT
            frame, position=checkLeftRight(frame,results,draw=True)
            
            if position=="Left" and x_pos_index!=0:
                pyautogui.press('left')
                x_pos_index-=1

            elif position=="Right" and x_pos_index!=2:
                pyautogui.press('right')
                x_pos_index+=1
            elif position=="Center":
                x_pos_index=1

            #JUMP AND CROUCH
            if MID_Y:
                frame, posture= checkJumpCrouch(frame, results, MID_Y, draw=True)

                current_time = time.time()

                if posture == "Jumping" and (current_time - last_jump_time) > JUMP_COOLDOWN:
                    pyautogui.press('up')
                    last_jump_time = current_time
                    y_pos_index = 2

                elif posture=="Crouching" and y_pos_index==1:
                    pyautogui.press('down')
                    y_pos_index=0
                elif posture=="Standing" and y_pos_index!=1:
                    y_pos_index=1

    curr_time=time.time()
    fps=int(1/(curr_time-prev_time)) if prev_time else 0
    prev_time=curr_time

    cv2.putText(frame, f"FPS:{fps}",(10,100), cv2.FONT_HERSHEY_PLAIN,2,(0,255,0),2)
    cv2.imshow("Subway Surfers with Pose Control", frame)

    if cv2.waitKey(1) & 0xFF==27:
        break
camera.release()
cv2.destroyAllWindows()

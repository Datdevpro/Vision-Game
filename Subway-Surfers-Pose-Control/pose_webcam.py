import cv2
import mediapipe as mp
import time

mp_pose=mp.solutions.pose
mp_drawing=mp.solutions.drawing_utils

cam=cv2.VideoCapture(0)

prev_time=0 

with mp_pose.Pose(
    static_image_mode=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
) as pose:
    
    while cam.isOpened():
        ret,frame=cam.read()
        if not ret:
            break

        original_frame=frame.copy()

        frame_rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        results=pose.process(frame_rgb)

        if results.pose_landmarks:
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS
            )

        original_frame=cv2.resize(original_frame,(640,480))
        frame=cv2.resize(frame,(640,480))

        combined=cv2.hconcat([original_frame,frame])

        #FPS CALCULATION
        curr_time=time.time()
        fps=1/(curr_time-prev_time) if prev_time!=0 else 0
        prev_time=curr_time

        #Display FPS
        cv2.putText(
            combined,
            f"FPS:{int(fps)}",
            (20,40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0,255,0),
            2
        )

        cv2.imshow("Normal | Pose Detection | FPS", combined)

        if cv2.waitKey(1) & 0xFF==ord('q'):
            break
cam.release()
cv2.destroyAllWindows
#!/usr/bin/env python3

# from io import open_code
import numpy as np
from numpy.core.arrayprint import printoptions
from numpy.linalg import pinv
from genpy.rostime import Duration
import rospy 
import rospkg 
from gazebo_msgs.msg import ModelState 
from gazebo_msgs.srv import SetModelState
import geometry_msgs.msg
import tf2_ros
from concurrent.futures import ThreadPoolExecutor

from tf.transformations import quaternion_from_euler

def target_traj_circle(t, begin, end, duration):
    theta = 2 * np.pi * 0.1 * t / 3 + np.arctan2(begin[1],begin[0])
    x = 19*np.sin(theta)
    y = 14*np.cos(theta)
    z = begin[2]
    yaw = -(theta + np.pi/2)
    pos = np.array([x, y, z])
    # return pos
    return np.array([x,y,z, 0, 0, yaw])

def target_traj_straight(t, begin, end, duration):
    trip = int(t / duration)

    if (trip % 2): # odd trip
        temp = begin
        begin = end
        end = temp

    max_dist = np.linalg.norm(begin-end)
    v_max = (end-begin) / duration
    pos = begin + v_max * (t - trip*duration)

    att = np.array([0,0,0])
    # return pos
    return np.concatenate([pos, att])

def set_drone_state(*args):
    args = args[0]
    model_name = args[0]
    traj_fn = args[1]
    begin = args[2]
    end = args[3]
    duration = args[4]
    
    br = tf2_ros.TransformBroadcaster()
    state_msg_0 = ModelState()
    state_msg_0.model_name = model_name
    state_msg_0.pose.position.x = begin[0]
    state_msg_0.pose.position.y = begin[1]
    state_msg_0.pose.position.z = begin[2]
    state_msg_0.pose.orientation.x = 0
    state_msg_0.pose.orientation.y = 0
    state_msg_0.pose.orientation.z = 0
    state_msg_0.pose.orientation.w = 1

    rospy.wait_for_service('/gazebo/set_model_state')
    start = rospy.get_rostime()
    elapsed = 0
    end_time = 60
    rate = rospy.Rate(100)
    while not rospy.is_shutdown():
    # while elapsed <= end_time:
        now = rospy.get_rostime()
        elapsed = (now - start).to_sec()
        rospy.wait_for_service('/gazebo/set_model_state')
        try:
            pose = traj_fn(elapsed, begin, end, duration)
            # print(elapsed, pos)
            state_msg_0.pose.position.x = pose[0]
            state_msg_0.pose.position.y = pose[1]
            state_msg_0.pose.position.z = pose[2]
            
            q_ = quaternion_from_euler(pose[3], pose[4], pose[5])
            state_msg_0.pose.orientation.x = q_[0]
            state_msg_0.pose.orientation.y = q_[1]
            state_msg_0.pose.orientation.z = q_[2]
            state_msg_0.pose.orientation.w = q_[3]
            
            set_state = rospy.ServiceProxy('/gazebo/set_model_state', SetModelState)
            resp = set_state( state_msg_0 )
            t = geometry_msgs.msg.TransformStamped()
            t.header.stamp = rospy.Time.now()
            t.header.frame_id = "map"
            t.child_frame_id = model_name
            t.transform.translation.x = state_msg_0.pose.position.x
            t.transform.translation.y = state_msg_0.pose.position.y
            t.transform.translation.z = state_msg_0.pose.position.z
            t.transform.rotation.x = state_msg_0.pose.orientation.x
            t.transform.rotation.y = state_msg_0.pose.orientation.y
            t.transform.rotation.z = state_msg_0.pose.orientation.z
            t.transform.rotation.w = state_msg_0.pose.orientation.w
            br.sendTransform(t)

        except rospy.ServiceException as e:
            print("Service call failed: {:s}".format(str(e)))
        rate.sleep()
    pass

def main():
    rospy.init_node('set_pose')
    x0_1 = np.array([-20, -5, 20])
    x0_2 = np.array([20, 5, 20])

    executor_args = [
        ["drone_0", target_traj_straight, x0_1, x0_1+[40,0,0], 60], 
        # ["drone_1", target_traj_straight, x0_2, x0_2+[-40,0,0], 30],
        # ["drone_0", target_traj_circle, [-10, 0, 18], [-10, 0, 18], 30],
        ["bird", target_traj_circle, [10,0,10], [10,0,10], 30],
    ]
    
    with ThreadPoolExecutor(max_workers=5) as tpe:
        print("started")
        tpe.map(set_drone_state, executor_args)

    rospy.spin()

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass

#!/usr/bin/env python

__author__ = 'aivanovic'

import rospy, math
from pid import PID
from geometry_msgs.msg import Vector3, PoseWithCovarianceStamped, PoseStamped, \
    TwistStamped, Pose, Point
from nav_msgs.msg import Odometry
from std_msgs.msg import Float64, Empty
from dynamic_reconfigure.server import Server
from mmuav_control.cfg import PositionCtlParamsConfig
from mmuav_msgs.msg import PIDController
from mmuav_msgs.msg import MotorSpeed
from mav_msgs.msg import Actuators
from rospkg import RosPack
import yaml

class PositionControl:
    '''
    Class implements ROS node for cascade (z, vz) PID control for MAV height.
    Subscribes to:
        /morus/pose       - used to extract z-position of the vehicle
        /morus/velocity   - used to extract vz of the vehicle
        /morus/pos_ref    - used to set the reference for z-position
        /morus/vel_ref    - used to set the reference for vz-position (useful for testing velocity controller)

    Publishes:
        /morus/mot_vel_ref  - referent value for thrust in terms of motor velocity (rad/s)
        /morus/pid_z        - publishes PID-z data - referent value, measured value, P, I, D and total component (useful for tuning params)
        /morus/pid_vz        - publishes PID-vz data - referent value, measured value, P, I, D and total component (useful for tuning params)

    Dynamic reconfigure is used to set controller params online.
    '''

    def __init__(self):
        '''
        Initialization of the class.
        '''

        self.start_flag = False         # indicates if we received the first measurement
        self.config_start = False       # flag indicates if the config callback is called for the first time

        # Load parameters from yaml file
        file_name = rospy.get_param('filename', 'PositionControl.yaml')
        file_name = RosPack().get_path('mmuav_control') + '/config/' + file_name
        initial_params = yaml.load(file(file_name, 'r'))

        #                              (m_uav + m_arms)/(C*4)
        self.mot_speed_hover = math.sqrt(9.81*(initial_params['mass'])/(
            initial_params['rotor_c']*initial_params['rotor_num']))

        self.pos_sp = Point()
        self.pos_sp.z = 1.0
        self.pos_mv = Point()
        self.vel_mv = Vector3()

        # X controller
        self.pid_x = PID()
        self.pid_vx = PID()

        # Y controller
        self.pid_y = PID()
        self.pid_vy = PID()

        # Z controller
        self.pid_z = PID()              # pid instance for z control
        self.pid_vz = PID()             # pid instance for z-velocity control

        #########################################################
        #########################################################

        # Add parameters for x controller
        self.pid_x.set_kp(initial_params['pid_x']['Kp'])
        self.pid_x.set_ki(initial_params['pid_x']['Ki'])
        self.pid_x.set_kd(initial_params['pid_x']['Kd'])
        self.pid_x.set_lim_high(initial_params['pid_x']['limit']['high'])
        self.pid_x.set_lim_low(initial_params['pid_x']['limit']['low'])

        # Add parameters for vx controller
        self.pid_vx.set_kp(initial_params['pid_vx']['Kp'])
        self.pid_vx.set_ki(initial_params['pid_vx']['Ki'])
        self.pid_vx.set_kd(initial_params['pid_vx']['Kd'])
        self.pid_vx.set_lim_high(initial_params['pid_vx']['limit']['high'])
        self.pid_vx.set_lim_low(initial_params['pid_vx']['limit']['low'])

        # Add parameters for y controller
        self.pid_y.set_kp(initial_params['pid_y']['Kp'])
        self.pid_y.set_ki(initial_params['pid_y']['Ki'])
        self.pid_y.set_kd(initial_params['pid_y']['Kd'])
        self.pid_y.set_lim_high(initial_params['pid_y']['limit']['high'])
        self.pid_y.set_lim_low(initial_params['pid_y']['limit']['low'])

        # Add parameters for vy controller
        self.pid_vy.set_kp(initial_params['pid_vy']['Kp'])
        self.pid_vy.set_ki(initial_params['pid_vy']['Ki'])
        self.pid_vy.set_kd(initial_params['pid_vy']['Kd'])
        self.pid_vy.set_lim_high(initial_params['pid_vy']['limit']['high'])
        self.pid_vy.set_lim_low(initial_params['pid_vy']['limit']['low'])

        # Add parameters for z controller
        self.pid_z.set_kp(initial_params['pid_z']['Kp'])
        self.pid_z.set_ki(initial_params['pid_z']['Ki'])
        self.pid_z.set_kd(initial_params['pid_z']['Kd'])
        self.pid_z.set_lim_high(initial_params['pid_z']['limit']['high'])
        self.pid_z.set_lim_low(initial_params['pid_z']['limit']['low'])

        # Add parameters for vz controller
        self.pid_vz.set_kp(initial_params['pid_vz']['Kp'])
        self.pid_vz.set_ki(initial_params['pid_vz']['Ki'])
        self.pid_vz.set_kd(initial_params['pid_vz']['Kd'])
        self.pid_vz.set_lim_high(initial_params['pid_vz']['limit']['high'])
        self.pid_vz.set_lim_low(initial_params['pid_vz']['limit']['low'])
        #########################################################
        #########################################################

        self.mot_speed = 0              # referent motors velocity, computed by PID cascade

        self.t_old = 0

        rospy.Subscriber('pose', PoseStamped, self.pose_cb)
        rospy.Subscriber('odometry', Odometry, self.vel_cb)
        rospy.Subscriber('vel_ref', Vector3, self.vel_ref_cb)
        rospy.Subscriber('pose_ref', Pose, self.pose_ref_cb)
        rospy.Subscriber('reset_controllers', Empty, self.reset_controllers_cb)
        self.pub_pid_x = rospy.Publisher('pid_x', PIDController, queue_size=1)
        self.pub_pid_vx = rospy.Publisher('pid_vx', PIDController, queue_size=1)
        self.pub_pid_y = rospy.Publisher('pid_y', PIDController, queue_size=1)
        self.pub_pid_vy = rospy.Publisher('pid_vy', PIDController, queue_size=1)
        self.pub_pid_z = rospy.Publisher('pid_z', PIDController, queue_size=1)
        self.pub_pid_vz = rospy.Publisher('pid_vz', PIDController, queue_size=1)
        self.mot_ref_pub = rospy.Publisher('mot_vel_ref', Float64, queue_size=1)
        self.euler_ref_pub = rospy.Publisher('euler_ref', Vector3, queue_size=1)

        #self.pub_gm_mot = rospy.Publisher('collectiveThrust', GmStatus, queue_size=1)       
        self.cfg_server = Server(PositionCtlParamsConfig, self.cfg_callback)
        self.rate = rospy.get_param('rate', 100)
        self.ros_rate = rospy.Rate(self.rate)                 # attitude control at 100 Hz
        self.t_start = rospy.Time.now()

    def run(self):
        '''
        Runs ROS node - computes PID algorithms for z and vz control.
        '''

        while not self.start_flag and not rospy.is_shutdown():
            print 'Waiting for pose measurements.'
            rospy.sleep(0.5)
        print "Starting height control."

        self.t_old = rospy.Time.now()
        #self.t_old = datetime.now()

        while not rospy.is_shutdown():

            while not self.start_flag and not rospy.is_shutdown():
                print 'Waiting for pose measurements.'
                rospy.sleep(0.5)

            rospy.sleep(1.0/float(self.rate))

            ########################################################
            ########################################################
            # Implement cascade PID control here.
            # Reference for z is stored in self.z_sp.
            # Measured z-position is stored in self.z_mv.
            # If you want to test only vz - controller, the corresponding reference is stored in self.vz_sp.
            # Measured vz-velocity is stored in self.vz_mv
            # Resultant referent value for motor velocity should be stored in variable mot_speed.
            # When you implement attitude control set the flag self.attitude_ctl to 1

            #self.gm_attitude_ctl = 1  # don't forget to set me to 1 when you implement attitude ctl
            t = rospy.Time.now()
            dt = (t - self.t_old).to_sec()
            #t = datetime.now()
            #dt = (t - self.t_old).total_seconds()
            if dt > 1.05/float(self.rate) or dt < 0.95/float(self.rate):
                #print dt
                pass
            self.t_old = t

            temp_euler_ref = Vector3()
            vx_ref = self.pid_x.compute(self.pos_sp.x, self.pos_mv.x, dt)
            temp_euler_ref.y = self.pid_vx.compute(vx_ref, self.vel_mv.x, dt)
            vy_ref = self.pid_y.compute(self.pos_sp.y, self.pos_mv.y, dt)
            temp_euler_ref.x = -self.pid_vy.compute(vy_ref, self.vel_mv.y, dt)


            vz_ref = self.pid_z.compute(self.pos_sp.z, self.pos_mv.z, dt)
            self.mot_speed = self.mot_speed_hover + \
                        self.pid_vz.compute(vz_ref, self.vel_mv.z, dt)
            #print "mot_speed", self.mot_speed

            ########################################################
            ########################################################

            # Publish to euler ref
            self.euler_ref_pub.publish(temp_euler_ref)

            # gas motors are used to control attitude
            # publish referent motor velocity to attitude controller
            mot_speed_msg = Float64(self.mot_speed)
            self.mot_ref_pub.publish(mot_speed_msg)


            # Publish PID data - could be useful for tuning
            self.pub_pid_x.publish(self.pid_x.create_msg())
            self.pub_pid_vx.publish(self.pid_vx.create_msg())
            self.pub_pid_y.publish(self.pid_y.create_msg())
            self.pub_pid_vy.publish(self.pid_vy.create_msg())
            self.pub_pid_z.publish(self.pid_z.create_msg())
            self.pub_pid_vz.publish(self.pid_vz.create_msg())

    def reset_controllers_cb(self, msg):
        self.start_flag = False
        self.pid_x.reset()
        self.pid_vx.reset()
        self.pid_y.reset()
        self.pid_vy.reset()
        self.pid_z.reset()
        #self.pid_z.ui_old = 22.0
        self.pid_vz.reset()
        rospy.Subscriber('odometry', Odometry, self.vel_cb)
        rospy.Subscriber('pose', PoseStamped, self.pose_cb)

    def pose_cb(self, msg):
        '''
        Pose (6DOF - position and orientation) callback.
        :param msg: Type PoseWithCovarianceStamped
        '''
        if not self.start_flag:
            self.start_flag = True
        
        self.pos_mv = msg.pose.position

    def vel_cb(self, msg):
        '''
        Velocity callback (linear velocity - x,y,z)
        :param msg: Type Vector3Stamped
        '''
        #if not self.start_flag:
        #    self.start_flag = True
        self.vel_mv = msg.twist.twist.linear

    def vel_ref_cb(self, msg):
        '''
        Referent velocity callback. Use received velocity values when during initial tuning
        velocity controller (i.e. when position controller still not implemented).
        :param msg: Type Vector3
        '''
        self.vx_sp = msg.x
        self.vy_sp = msg.y
        self.vz_sp = msg.z

    def pose_ref_cb(self, msg):
        '''
        Referent position callback. Received value (z-component) is used as a referent height.
        :param msg: Type Vector3
        '''
        self.pos_sp = msg.position

    def cfg_callback(self, config, level):
        """
        Callback for dynamically reconfigurable parameters (P,I,D gains for height and velocity controller)
        """
        #print "CFG callback"

        if not self.config_start:
            # callback is called for the first time. Use this to set the new params to the config server
            config.x_kp = self.pid_x.get_kp()
            config.x_ki = self.pid_x.get_ki()
            config.x_kd = self.pid_x.get_kd()

            config.vx_kp = self.pid_vx.get_kp()
            config.vx_ki = self.pid_vx.get_ki()
            config.vx_kd = self.pid_vx.get_kd()

            config.y_kp = self.pid_y.get_kp()
            config.y_ki = self.pid_y.get_ki()
            config.y_kd = self.pid_y.get_kd()

            config.vy_kp = self.pid_vy.get_kp()
            config.vy_ki = self.pid_vy.get_ki()
            config.vy_kd = self.pid_vy.get_kd()

            config.z_kp = self.pid_z.get_kp()
            config.z_ki = self.pid_z.get_ki()
            config.z_kd = self.pid_z.get_kd()

            config.vz_kp = self.pid_vz.get_kp()
            config.vz_ki = self.pid_vz.get_ki()
            config.vz_kd = self.pid_vz.get_kd()

            self.config_start = True
        else:
            # The following code just sets up the P,I,D gains for all controllers
            self.pid_x.set_kp(config.x_kp)
            self.pid_x.set_ki(config.x_ki)
            self.pid_x.set_kd(config.x_kd)

            self.pid_vx.set_kp(config.vx_kp)
            self.pid_vx.set_ki(config.vx_ki)
            self.pid_vx.set_kd(config.vx_kd)

            self.pid_y.set_kp(config.y_kp)
            self.pid_y.set_ki(config.y_ki)
            self.pid_y.set_kd(config.y_kd)

            self.pid_vy.set_kp(config.vy_kp)
            self.pid_vy.set_ki(config.vy_ki)
            self.pid_vy.set_kd(config.vy_kd)

            self.pid_z.set_kp(config.z_kp)
            self.pid_z.set_ki(config.z_ki)
            self.pid_z.set_kd(config.z_kd)

            self.pid_vz.set_kp(config.vz_kp)
            self.pid_vz.set_ki(config.vz_ki)
            self.pid_vz.set_kd(config.vz_kd)

        # this callback should return config data back to server
        return config

if __name__ == '__main__':

    rospy.init_node('position_controller')
    position_ctl = PositionControl()
    position_ctl.run()


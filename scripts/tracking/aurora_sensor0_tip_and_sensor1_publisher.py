#!/usr/bin/env python3

# =============================================================
# INPUT
# /aurora/sensor0 = penna
# /aurora/sensor1 = sensore montato sull'endoscopio
#
# OUTPUT
# /aurora_pose_1 = punta calibrata della penna
# /aurora_pose_2 = posa del sensore dell'endoscopio
#
# Non viene utilizzato alcun fallback tra i due sensori.
# =============================================================

import math
import sys

import numpy as np
import rclpy

from rclpy.node import Node
from rclpy.qos import QoSProfile

from aurora_ndi_ros2_driver.msg import AuroraData
from geometry_msgs.msg import PoseStamped


def normalize_quaternion(
    qx: float,
    qy: float,
    qz: float,
    qw: float
):
    norm = math.sqrt(
        qx * qx +
        qy * qy +
        qz * qz +
        qw * qw
    )

    if norm < 1e-12:
        return None

    return (
        qx / norm,
        qy / norm,
        qz / norm,
        qw / norm
    )


def quaternion_to_rotation_matrix(
    qx: float,
    qy: float,
    qz: float,
    qw: float
) -> np.ndarray:

    quaternion = normalize_quaternion(
        qx,
        qy,
        qz,
        qw
    )

    if quaternion is None:
        raise ValueError(
            "Quaternione nullo o non valido"
        )

    qx, qy, qz, qw = quaternion

    return np.array(
        [
            [
                1.0 - 2.0 * (qy * qy + qz * qz),
                2.0 * (qx * qy - qz * qw),
                2.0 * (qx * qz + qy * qw)
            ],
            [
                2.0 * (qx * qy + qz * qw),
                1.0 - 2.0 * (qx * qx + qz * qz),
                2.0 * (qy * qz - qx * qw)
            ],
            [
                2.0 * (qx * qz - qy * qw),
                2.0 * (qy * qz + qx * qw),
                1.0 - 2.0 * (qx * qx + qy * qy)
            ]
        ],
        dtype=float
    )


def is_zero_pose(
    msg: AuroraData,
    pos_tol: float = 1e-9,
    quat_tol: float = 1e-9
) -> bool:

    position = msg.position
    orientation = msg.orientation

    position_is_zero = (
        abs(position.x) < pos_tol and
        abs(position.y) < pos_tol and
        abs(position.z) < pos_tol
    )

    quaternion_is_identity = (
        abs(orientation.x) < quat_tol and
        abs(orientation.y) < quat_tol and
        abs(orientation.z) < quat_tol and
        abs(orientation.w - 1.0) < quat_tol
    )

    return (
        position_is_zero and
        quaternion_is_identity
    )


class AuroraPublisher(Node):

    def __init__(self):
        super().__init__(
            "aurora_pen_and_endoscope_publisher"
        )

        # =====================================================
        # PARAMETRI TOPIC
        # =====================================================

        self.declare_parameter(
            "sensor0_topic",
            "/aurora/sensor0"
        )

        self.declare_parameter(
            "sensor1_topic",
            "/aurora/sensor1"
        )

        self.declare_parameter(
            "output_pose1_topic",
            "/aurora_pose_1"
        )

        self.declare_parameter(
            "output_pose2_topic",
            "/aurora_pose_2"
        )

        # =====================================================
        # OFFSET DELLA PUNTA DELLA PENNA
        # =====================================================

        self.declare_parameter(
            "pointer_offset_x",
            -3.272791
        )

        self.declare_parameter(
            "pointer_offset_y",
            0.076727
        )

        self.declare_parameter(
            "pointer_offset_z",
            -4.370850
        )

        # =====================================================
        # VALIDAZIONE DATI AURORA
        # =====================================================

        self.declare_parameter(
            "require_visible",
            True
        )

        self.declare_parameter(
            "ignore_zero_pose",
            True
        )

        self.declare_parameter(
            "max_error",
            1e9
        )

        sensor0_topic = self.get_parameter(
            "sensor0_topic"
        ).value

        sensor1_topic = self.get_parameter(
            "sensor1_topic"
        ).value

        output_pose1_topic = self.get_parameter(
            "output_pose1_topic"
        ).value

        output_pose2_topic = self.get_parameter(
            "output_pose2_topic"
        ).value

        self.pointer_offset = np.array(
            [
                float(
                    self.get_parameter(
                        "pointer_offset_x"
                    ).value
                ),
                float(
                    self.get_parameter(
                        "pointer_offset_y"
                    ).value
                ),
                float(
                    self.get_parameter(
                        "pointer_offset_z"
                    ).value
                )
            ],
            dtype=float
        )

        self.require_visible = bool(
            self.get_parameter(
                "require_visible"
            ).value
        )

        self.ignore_zero_pose = bool(
            self.get_parameter(
                "ignore_zero_pose"
            ).value
        )

        self.max_error = float(
            self.get_parameter(
                "max_error"
            ).value
        )

        # =====================================================
        # PUBLISHER E SUBSCRIBER
        # =====================================================

        qos = QoSProfile(depth=10)

        self.pub_pose1 = self.create_publisher(
            PoseStamped,
            output_pose1_topic,
            qos
        )

        self.pub_pose2 = self.create_publisher(
            PoseStamped,
            output_pose2_topic,
            qos
        )

        self.sub_sensor0 = self.create_subscription(
            AuroraData,
            sensor0_topic,
            self.cb_sensor0,
            qos
        )

        self.sub_sensor1 = self.create_subscription(
            AuroraData,
            sensor1_topic,
            self.cb_sensor1,
            qos
        )

        self.get_logger().info(
            f"Penna: {sensor0_topic} "
            f"-> {output_pose1_topic}"
        )

        self.get_logger().info(
            f"Endoscopio: {sensor1_topic} "
            f"-> {output_pose2_topic}"
        )

        self.get_logger().info(
            "Offset punta penna = "
            f"[{self.pointer_offset[0]:.6f}, "
            f"{self.pointer_offset[1]:.6f}, "
            f"{self.pointer_offset[2]:.6f}] mm"
        )

    # =========================================================
    # VALIDAZIONE MESSAGGI
    # =========================================================

    def is_valid_msg(
        self,
        msg: AuroraData
    ) -> bool:

        if self.require_visible and not msg.visible:
            return False

        if not math.isfinite(msg.error):
            return False

        if msg.error > self.max_error:
            return False

        if self.ignore_zero_pose and is_zero_pose(msg):
            return False

        quaternion = normalize_quaternion(
            msg.orientation.x,
            msg.orientation.y,
            msg.orientation.z,
            msg.orientation.w
        )

        if quaternion is None:
            return False

        return True

    # =========================================================
    # CONVERSIONE DIRETTA A POSESTAMPED
    # =========================================================

    def aurora_to_pose_stamped(
        self,
        msg: AuroraData
    ) -> PoseStamped:

        pose = PoseStamped()

        pose.header = msg.header

        pose.pose.position.x = float(
            msg.position.x
        )

        pose.pose.position.y = float(
            msg.position.y
        )

        pose.pose.position.z = float(
            msg.position.z
        )

        normalized_quaternion = normalize_quaternion(
            msg.orientation.x,
            msg.orientation.y,
            msg.orientation.z,
            msg.orientation.w
        )

        if normalized_quaternion is not None:
            qx, qy, qz, qw = normalized_quaternion

            pose.pose.orientation.x = float(qx)
            pose.pose.orientation.y = float(qy)
            pose.pose.orientation.z = float(qz)
            pose.pose.orientation.w = float(qw)

        return pose

    # =========================================================
    # CALCOLO DELLA PUNTA DELLA PENNA
    # =========================================================

    def sensor0_to_pen_tip_pose(
        self,
        msg: AuroraData
    ):

        position = msg.position
        orientation = msg.orientation

        try:
            rotation_matrix = (
                quaternion_to_rotation_matrix(
                    orientation.x,
                    orientation.y,
                    orientation.z,
                    orientation.w
                )
            )

        except ValueError:
            return None

        offset_column = self.pointer_offset.reshape(
            3,
            1
        )

        sensor_position = np.array(
            [
                [position.x],
                [position.y],
                [position.z]
            ],
            dtype=float
        )

        pen_tip_position = (
            rotation_matrix @ offset_column
        ) + sensor_position

        pen_tip_pose = PoseStamped()

        pen_tip_pose.header = msg.header

        pen_tip_pose.pose.position.x = float(
            pen_tip_position[0, 0]
        )

        pen_tip_pose.pose.position.y = float(
            pen_tip_position[1, 0]
        )

        pen_tip_pose.pose.position.z = float(
            pen_tip_position[2, 0]
        )

        normalized_quaternion = normalize_quaternion(
            orientation.x,
            orientation.y,
            orientation.z,
            orientation.w
        )

        if normalized_quaternion is None:
            return None

        qx, qy, qz, qw = normalized_quaternion

        pen_tip_pose.pose.orientation.x = float(qx)
        pen_tip_pose.pose.orientation.y = float(qy)
        pen_tip_pose.pose.orientation.z = float(qz)
        pen_tip_pose.pose.orientation.w = float(qw)

        return pen_tip_pose

    # =========================================================
    # SENSOR0 = PENNA
    # =========================================================

    def cb_sensor0(
        self,
        msg: AuroraData
    ):

        if not self.is_valid_msg(msg):
            return

        pen_tip_pose = self.sensor0_to_pen_tip_pose(
            msg
        )

        if pen_tip_pose is None:
            return

        # Pubblica soltanto /aurora_pose_1.
        self.pub_pose1.publish(
            pen_tip_pose
        )

    # =========================================================
    # SENSOR1 = ENDOSCOPIO
    # =========================================================

    def cb_sensor1(
        self,
        msg: AuroraData
    ):

        if not self.is_valid_msg(msg):
            return

        endoscope_pose = (
            self.aurora_to_pose_stamped(msg)
        )

        # Pubblica soltanto /aurora_pose_2.
        self.pub_pose2.publish(
            endoscope_pose
        )


def main():
    rclpy.init()

    node = AuroraPublisher()

    try:
        print(
            f"ESEGUIBILE: {sys.executable}"
        )

        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
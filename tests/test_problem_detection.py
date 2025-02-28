import unittest
from unittest.mock import MagicMock
from problem_detection import ProblemDetector
import time


class TestProblemDetector(unittest.TestCase):
    def setUp(self):
        # Vor jedem Test
        self.mock_mqtt_handler = MagicMock()
        self.problem_detector = ProblemDetector(self.mock_mqtt_handler,
                                                threshold_time=1)  # Geringe threshold_time für Tests

    def test_add_position(self):
        # Testdaten
        gps_data = {"lat": 46.811819, "lon": 7.132838, "timestamp": time.time()}
        # Funktion aufrufen
        self.problem_detector.add_position(gps_data)

    def test_check_for_problem_no_problem(self):
        # Testdaten
        gps_data = {"lat": 46.811819, "lon": 7.132838, "timestamp": time.time()}
        # mehrmals aufrufen um die Historie zu füllen
        for x in range(5):
            self.problem_detector.add_position(gps_data)
            time.sleep(0.1)
        # Überprüfen ob die Funktion nicht aufgerufen wurde
        self.mock_mqtt_handler.publish_message.assert_not_called()

    def test_check_for_problem_with_problem(self):
        # Testdaten
        gps_data1 = {"lat": 46.811819, "lon": 7.132838, "timestamp": time.time()}
        gps_data2 = {"lat": 46.811819, "lon": 7.132838, "timestamp": time.time() + 1}  # 1s später
        # mehrmals aufrufen um die Historie zu füllen
        for x in range(5):
            self.problem_detector.add_position(gps_data1)
            time.sleep(0.1)
        self.problem_detector.add_position(gps_data2)
        # Überprüfen ob die Funktion aufgerufen wurde
        self.mock_mqtt_handler.publish_message.assert_called_with(self.mock_mqtt_handler.topic_control, "problem")

    def test_check_for_problem_no_data(self):
        self.problem_detector.add_position(None)
        self.mock_mqtt_handler.publish_message.assert_not_called()

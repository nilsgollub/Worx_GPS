# tests/test_problem_detection.py
import unittest
from unittest.mock import MagicMock, call, patch
import time
from collections import deque
from problem_detection import ProblemDetector

class TestProblemDetector(unittest.TestCase):
    """
    Testet die ProblemDetector Klasse.
    """

    def setUp(self):
        """
        Setzt die Testumgebung für jeden Test auf.
        """
        self.mock_mqtt_handler = MagicMock()
        self.test_topic_control = "test/worx/control"
        self.mock_mqtt_handler.topic_control = self.test_topic_control

        # Initialisiere ProblemDetector mit kurzer Threshold-Zeit für Tests
        self.threshold_time = 1.0 # 1 Sekunde
        self.problem_detector = ProblemDetector(self.mock_mqtt_handler, threshold_time=self.threshold_time)

        # Stelle sicher, dass die Deque korrekt initialisiert wurde
        self.assertIsInstance(self.problem_detector.position_history, deque)
        self.assertEqual(self.problem_detector.position_history.maxlen, 10)
        self.assertEqual(self.problem_detector.last_problem_time, 0)

    def test_add_position_none(self):
        """Testet das Hinzufügen von None als Position."""
        initial_len = len(self.problem_detector.position_history)
        self.problem_detector.add_position(None)
        # History sollte unverändert sein, check_for_problem nicht aufgerufen werden
        self.assertEqual(len(self.problem_detector.position_history), initial_len)
        # (check_for_problem wird intern aufgerufen, aber wir können prüfen, ob publish aufgerufen wurde)
        self.mock_mqtt_handler.publish_message.assert_not_called()

    def test_add_position_valid(self):
        """Testet das Hinzufügen einer gültigen Position."""
        pos1 = {"lat": 46.1, "lon": 7.1, "timestamp": time.time()}
        self.problem_detector.add_position(pos1)
        self.assertEqual(len(self.problem_detector.position_history), 1)
        self.assertEqual(self.problem_detector.position_history[0], (pos1["lat"], pos1["lon"], pos1["timestamp"]))

        pos2 = {"lat": 46.2, "lon": 7.2, "timestamp": time.time() + 0.5}
        self.problem_detector.add_position(pos2)
        self.assertEqual(len(self.problem_detector.position_history), 2)
        self.assertEqual(self.problem_detector.position_history[1], (pos2["lat"], pos2["lon"], pos2["timestamp"]))

    def test_check_for_problem_not_enough_data(self):
        """Testet check_for_problem, wenn nicht genug Daten vorhanden sind (< 5)."""
        current_time = time.time()
        for i in range(4):
            pos = {"lat": 46.1, "lon": 7.1, "timestamp": current_time + i * 0.1}
            self.problem_detector.add_position(pos)

        # add_position ruft check_for_problem intern auf.
        # Da weniger als 5 Punkte da sind, sollte kein Problem gemeldet werden.
        self.mock_mqtt_handler.publish_message.assert_not_called()

    def test_check_for_problem_no_problem_moving(self):
        """Testet check_for_problem, wenn sich das Gerät bewegt (kein Problem)."""
        current_time = time.time()
        # Füge 10 unterschiedliche Positionen hinzu
        for i in range(10):
            pos = {"lat": 46.1 + i * 0.0001, "lon": 7.1 + i * 0.0001, "timestamp": current_time + i * 0.2}
            self.problem_detector.add_position(pos)
            time.sleep(0.01) # Kleine Pause simulieren

        # Auch nach 10 Punkten sollte kein Problem gemeldet werden, da Bewegung stattfand
        self.mock_mqtt_handler.publish_message.assert_not_called()

    def test_check_for_problem_is_problem_standing_still(self):
        """Testet check_for_problem, wenn das Gerät stillsteht (Problem)."""
        lat, lon = 46.1, 7.1
        start_time = time.time()

        # Füge 10 gleiche Positionen über einen Zeitraum > threshold_time hinzu
        for i in range(10):
            # Zeitstempel erhöhen, um die threshold_time zu überschreiten
            timestamp = start_time + i * (self.threshold_time / 8) # Überschreitet Schwelle nach ~8 Punkten
            pos = {"lat": lat, "lon": lon, "timestamp": timestamp}
            self.problem_detector.add_position(pos)
            # Kleine Pause, um sicherzustellen, dass time.time() sich auch ändert
            # (obwohl der Timestamp im Test entscheidend ist)
            # time.sleep(0.01)

        # Problem sollte erkannt und gemeldet werden
        self.mock_mqtt_handler.publish_message.assert_called_once_with(
            self.test_topic_control, "problem"
        )
        # last_problem_time sollte gesetzt worden sein
        self.assertGreater(self.problem_detector.last_problem_time, 0)
        # Prüfe, ob die Zeit nahe der aktuellen Zeit liegt
        self.assertAlmostEqual(self.problem_detector.last_problem_time, time.time(), delta=1.0)


    def test_check_for_problem_cooldown(self):
        """Testet, dass nach einem Problem eine Sperre (Cooldown) aktiv ist."""
        lat, lon = 46.1, 7.1
        start_time = time.time()

        # 1. Problem auslösen
        for i in range(10):
            timestamp = start_time + i * (self.threshold_time / 8)
            pos = {"lat": lat, "lon": lon, "timestamp": timestamp}
            self.problem_detector.add_position(pos)

        self.mock_mqtt_handler.publish_message.assert_called_once_with(self.test_topic_control, "problem")
        first_problem_time = self.problem_detector.last_problem_time
        self.assertGreater(first_problem_time, 0)
        self.mock_mqtt_handler.publish_message.reset_mock() # Reset für nächsten Check

        # 2. Erneut versuchen, Problem auszulösen (innerhalb der 60s Sperre)
        # Füge weitere stehende Positionen hinzu
        current_time = time.time()
        for i in range(5):
             # Zeitstempel weiter erhöhen, Bedingung wäre erfüllt
            timestamp = current_time + i * 0.1
            pos = {"lat": lat, "lon": lon, "timestamp": timestamp}
            self.problem_detector.add_position(pos)

        # Kein weiteres Problem sollte gemeldet werden wegen der Sperre
        self.mock_mqtt_handler.publish_message.assert_not_called()
        # last_problem_time sollte unverändert sein
        self.assertEqual(self.problem_detector.last_problem_time, first_problem_time)

    @patch('problem_detection.time.time')
    def test_check_for_problem_after_cooldown(self, mock_time):
        """Testet, dass nach Ablauf der Sperre wieder ein Problem gemeldet wird."""
        lat, lon = 46.1, 7.1
        start_time = 1000.0 # Feste Startzeit für den Test
        mock_time.return_value = start_time

        # 1. Problem auslösen
        for i in range(10):
            timestamp = start_time + i * (self.threshold_time / 8)
            pos = {"lat": lat, "lon": lon, "timestamp": timestamp}
            self.problem_detector.add_position(pos)

        self.mock_mqtt_handler.publish_message.assert_called_once_with(self.test_topic_control, "problem")
        # last_problem_time wird auf mock_time (1000.0) gesetzt
        self.assertEqual(self.problem_detector.last_problem_time, start_time)
        self.mock_mqtt_handler.publish_message.reset_mock()

        # 2. Zeit vorspulen (um mehr als 60 Sekunden)
        mock_time.return_value = start_time + 70.0
        current_time = start_time + 70.0

        # 3. Erneut Problem auslösen (nach Ablauf der Sperre)
        # Füge weitere stehende Positionen hinzu
        for i in range(10):
            # Zeitstempel weiter erhöhen, Bedingung wäre erfüllt
            timestamp = current_time + i * (self.threshold_time / 8)
            pos = {"lat": lat, "lon": lon, "timestamp": timestamp}
            self.problem_detector.add_position(pos)

        # Problem sollte erneut gemeldet werden
        self.mock_mqtt_handler.publish_message.assert_called_once_with(self.test_topic_control, "problem")
        # last_problem_time sollte aktualisiert worden sein
        self.assertEqual(self.problem_detector.last_problem_time, current_time)


if __name__ == '__main__':
    unittest.main()

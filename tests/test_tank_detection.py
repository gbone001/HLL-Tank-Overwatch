import unittest

from enhanced_discord_bot import detect_tank_kill


class TankDetectionTests(unittest.TestCase):
    def setUp(self):
        self.keywords = {
            "cannons": ["75mm", "88mm"],
            "launchers": ["panzerschreck"]
        }

    def test_weapon_keyword_triggers_detection(self):
        payload = {
            "weapon": "75mm AP Shell",
            "killer_name": "Able Gunner",
            "killer_team": "Allies",
            "victim_name": "Axis Tank",
            "victim_team": "Axis",
            "target_vehicle": "Panther"
        }

        detection = detect_tank_kill(payload, self.keywords)
        self.assertIsNotNone(detection)
        self.assertEqual(detection.keyword_group, "cannons")
        self.assertEqual(detection.killer_name, "Able Gunner")
        self.assertEqual(detection.vehicle.lower(), "panther")

    def test_vehicle_class_falls_back_to_detection(self):
        payload = {
            "data": {
                "victim_vehicle_class": "Heavy_Tank",
                "weapon": "Satchel Charge",
                "attacker_name": "Axis Saboteur",
                "attacker_team": "Axis",
                "target_name": "Sherman Crew",
                "target_team": "Allies"
            }
        }

        detection = detect_tank_kill(payload, self.keywords)
        self.assertIsNotNone(detection)
        self.assertEqual(detection.keyword_group, "vehicle_class")
        self.assertEqual(detection.keyword_match, "Heavy_Tank")
        self.assertEqual(detection.victim_team, "Allies")

    def test_non_tank_weapon_is_ignored(self):
        payload = {
            "weapon": "M1 Garand",
            "killer_team": "Allies",
            "victim_team": "Axis"
        }

        detection = detect_tank_kill(payload, self.keywords)
        self.assertIsNone(detection)

    def test_non_dict_payload_is_ignored(self):
        self.assertIsNone(detect_tank_kill("raw string", self.keywords))
        self.assertIsNone(detect_tank_kill(None, self.keywords))

    def test_partial_fields_still_produce_detection(self):
        payload = {
            "weapon": "88mm cannon",
        }
        detection = detect_tank_kill(payload, self.keywords)
        self.assertIsNotNone(detection)
        self.assertEqual(detection.weapon, "88mm cannon")


if __name__ == "__main__":
    unittest.main()

import unittest
import wikipedia_validator
import wikidata_processing
import common
import wikimedia_connection.wikimedia_connection as wikimedia_connection
import generate_webpage_with_error_output
import generate_overpass_query_output
import script
from tests_of_generate_osm_edits import *

class Tests(unittest.TestCase):
    def assert_linkability(self, type_id):
        is_unlinkable = wikipedia_validator.get_error_report_if_type_unlinkable_as_primary(type_id)
        if is_unlinkable != None:
            wikipedia_validator.dump_base_types_of_object_in_stdout(type_id, 'tests')
            print()
            print(is_unlinkable.error_message)
        self.assertEqual(None, is_unlinkable)

    def test_rejects_links_to_events(self):
        wikimedia_connection.set_cache_location(common.get_wikimedia_connection_cache_location())
        self.assertNotEqual(None, wikipedia_validator.get_error_report_if_type_unlinkable_as_primary('Q134301'))

    def test_rejects_links_to_spacecraft(self):
        wikimedia_connection.set_cache_location(common.get_wikimedia_connection_cache_location())
        self.assertNotEqual(None, wikipedia_validator.get_error_report_if_property_indicates_that_it_is_unlinkable_as_primary('Q2513'))

    def test_reject_links_to_humans(self):
        example_artist_id = 'Q561127'
        location = None
        forced_refresh = False
        self.assertNotEqual(None, wikipedia_validator.get_problem_based_on_wikidata_base_types(location, example_artist_id, forced_refresh))

    def test_complain_function(self):
        wikimedia_connection.set_cache_location(common.get_wikimedia_connection_cache_location())
        wikipedia_validator.complain_in_stdout_if_wikidata_entry_not_of_known_safe_type('Q824359', "explanation")

    def test_get_prerequisite_in_overpass_query_format(self):
        self.assertEqual(common.get_prerequisite_in_overpass_query_format({'prerequisite': {}}), "")

    def test_description_of_distance_return_string(self):
        example_city_wikidata_id = 'Q31487'
        self.assertEqual(type(""), type(wikipedia_validator.get_distance_description_between_location_and_wikidata_id((50, 20), example_city_wikidata_id)))

    def test_description_of_distance_return_string_for_missing_location(self):
        example_city_wikidata_id = 'Q31487'
        self.assertEqual(type(""), type(wikipedia_validator.get_distance_description_between_location_and_wikidata_id((None, None), example_city_wikidata_id)))

    def test_description_of_distance_return_string_for_missing_location_and_missing_location_in_wikidata(self):
        example_artist_id = 'Q561127'
        self.assertEqual(type(""), type(wikipedia_validator.get_distance_description_between_location_and_wikidata_id((None, None), example_artist_id)))

    def test_description_of_distance_return_string_for_missing_location_in_wikidata(self):
        example_artist_id = 'Q561127'
        self.assertEqual(type(""), type(wikipedia_validator.get_distance_description_between_location_and_wikidata_id((50, 20), example_artist_id)))

    def test_detecting_makro_as_invalid_primary_link(self):
        wikidata_id = 'Q704606'
        self.assertNotEqual(None, wikipedia_validator.get_error_report_if_type_unlinkable_as_primary(wikidata_id))

    def test_detecting_tesco_as_invalid_primary_link(self):
        wikidata_id = 'Q487494'
        self.assertNotEqual(None, wikipedia_validator.get_error_report_if_type_unlinkable_as_primary(wikidata_id))

    def test_detecting_carrefour_as_invalid_primary_link(self):
        wikidata_id = 'Q217599'
        self.assertNotEqual(None, wikipedia_validator.get_error_report_if_type_unlinkable_as_primary(wikidata_id))

    def test_detecting_cropp_as_invalid_primary_link(self):
        wikidata_id = 'Q9196793'
        self.assertNotEqual(None, wikipedia_validator.get_error_report_if_type_unlinkable_as_primary(wikidata_id))

    def test_overpass_escaping(self):
        before = {'wikipedia:de': "Zapiekle, Pickel's Vorwerk"}
        after = "['wikipedia:de'='Zapiekle, Pickel\\'s Vorwerk']"
        print(before)
        print(common.tag_dict_to_overpass_query_format(before))
        print(before)
        self.assertEqual(after, common.tag_dict_to_overpass_query_format(before))

    def test_detecting_castle_as_valid_primary_link(self):
        self.assert_linkability('Q2106892')

    def test_detecting_funicular_as_valid_primary_link(self):
        self.assert_linkability('Q5614426')

    def test_detecting_fast_tram_as_valid_primary_link(self):
        self.assert_linkability('Q1814872')

    def test_args_depending_code_for_behavior(self):
        wikimedia_connection.set_cache_location(common.get_wikimedia_connection_cache_location())
        #TODO - handle args. in test
        #wikipedia_validator.attempt_to_locate_wikipedia_tag_using_wikidata_id('Q2106892', False)

    def test_wikidata_ids_of_countries_with_language(self):
        self.assertEqual (['Q36'], wikipedia_validator.wikidata_ids_of_countries_with_language("pl"))
        self.assertEqual (('Q408' in wikipedia_validator.wikidata_ids_of_countries_with_language("en")), True)

if __name__ == '__main__':
    unittest.main()

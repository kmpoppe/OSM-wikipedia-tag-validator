import pprint
import argparse
import os
import wikimedia_connection.wikimedia_connection as wikimedia_connection
import osm_bot_abstraction_layer.osm_bot_abstraction_layer as osm_bot_abstraction_layer
import osm_handling_config.global_config as osm_handling_config
from wikibrain import wikimedia_link_issue_reporter
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import sqlite3
import json
import config

def parsed_args():
    parser = argparse.ArgumentParser(description='Production of webpage about validation of wikipedia tag in osm data.')
    parser.add_argument('-file', '-f', dest='file', type=str, help='name of yaml file produced by validator')
    args = parser.parse_args()
    if not (args.file):
        parser.error('Provide yaml file generated by wikipedia validator')
    return args

def get_nominatim_country_code(lat, lon):
    try:
        osm_bot_abstraction_layer.sleep(3)
        geolocator = Nominatim(user_agent="Wikipedia Validator", timeout=15)
        returned = geolocator.reverse(str(lat) + ", " + str(lon)).raw
        print(returned)
    except GeocoderTimedOut:
        osm_bot_abstraction_layer.sleep(20)
        return get_nominatim_country_code(lat, lon)
    if "address" not in returned:
        print(returned)
        print(link_to_point(lat, lon))
        raise "wat"
    return returned["address"]["country_code"]

def is_text_field_mentioning_wikipedia_or_wikidata(text):
    text = text.replace("http://wiki-de.genealogy.net/GOV:", "")
    if text.find("wikipedia") != -1:
        return True
    if text.find("wikidata") != -1:
        return True
    if text.find("wiki") != -1:
        return True
    return False

def note_or_fixme_review_request_indication(data):
    fixme = ""
    note = ""
    if 'fixme' in data['tag']:
        fixme = data['tag']['fixme']
    if 'note' in data['tag']:
        note = data['tag']['note']
    text_dump = "fixme=<" + fixme + "> note=<" + note + ">"
    if is_text_field_mentioning_wikipedia_or_wikidata(fixme):
        return text_dump
    if is_text_field_mentioning_wikipedia_or_wikidata(note):
        return text_dump
    return None

def load_errors(cursor, processed_area):
    cursor.execute("SELECT rowid, type, id, lat, lon, tags, area_identifier, download_timestamp, validator_complaint FROM osm_data WHERE validator_complaint IS NOT NULL AND validator_complaint <> '' AND area_identifier == :area_identifier", {"area_identifier": processed_area})
    returned = []
    for entry in cursor.fetchall():
        rowid, object_type, id, lat, lon, tags, area_identifier, updated, validator_complaint = entry
        tags = json.loads(tags)
        validator_complaint = json.loads(validator_complaint)
        returned.append(validator_complaint)
    return returned

def fit_wikipedia_edit_description_within_character_limit_new(new, reason):
    comment = "adding [wikipedia=" + new + "]" + reason
    if(len(comment)) > osm_bot_abstraction_layer.character_limit_of_description():
        comment = "adding wikipedia tag " + reason
    if(len(comment)) > osm_bot_abstraction_layer.character_limit_of_description():
        raise("comment too long")
    return comment

def fit_wikipedia_edit_description_within_character_limit_changed(now, new, reason):
    comment = "[wikipedia=" + now + "] to [wikipedia=" + new + "]" + reason
    if(len(comment)) > osm_bot_abstraction_layer.character_limit_of_description():
        comment = "changing wikipedia tag to <" + new + ">" + reason
    if(len(comment)) > osm_bot_abstraction_layer.character_limit_of_description():
        comment = "changing wikipedia tag " + reason
    if(len(comment)) > osm_bot_abstraction_layer.character_limit_of_description():
        raise("comment too long")
    return comment

def get_and_verify_data(e):
    print(e)
    print(e['osm_object_url'])
    return osm_bot_abstraction_layer.get_and_verify_data(e['osm_object_url'], e['prerequisite'], prerequisite_failure_callback=note_or_fixme_review_request_indication)

def desired_wikipedia_target_from_report(e):
    desired = None
    if e['proposed_tagging_changes'] != None:
        for change in e['proposed_tagging_changes']:
            if "wikipedia" in change["to"]:
                if desired != None:
                    raise ValueError("multiple incoming replacements of the same tag")
                desired = change["to"]["wikipedia"]
    if desired == None:
        raise Exception("Expected wikipedia tag to be provided")
    return desired

def handle_follow_wikipedia_redirect(e):
    if e['error_id'] != 'wikipedia wikidata mismatch - follow wikipedia redirect':
        return
    data = get_and_verify_data(e)
    if data == None:
        return None
    if is_edit_allowed_object_based_on_location(e['osm_object_url'], data, "pl", detailed_verification_function_is_within_given_country) == False:
        announce_skipping_object_as_outside_area(e['osm_object_url']+" (handle_follow_wikipedia_redirect funtion)")
    now = data['tag']['wikipedia']
    new = desired_wikipedia_target_from_report(e)
    reason = ", as current tag is a redirect and the new page matches present wikidata"
    comment = fit_wikipedia_edit_description_within_character_limit_changed(now, new, reason)
    data['tag']['wikipedia'] = new
    discussion_url = "https://forum.openstreetmap.org/viewtopic.php?id=59649"
    osm_wiki_documentation_page = "https://wiki.openstreetmap.org/wiki/Mechanical_Edits/Mateusz_Konieczny_-_bot_account/fixing_wikipedia_tags_pointing_at_redirects_in_Poland"
    automatic_status = osm_bot_abstraction_layer.fully_automated_description()
    type = e['osm_object_url'].split("/")[3]
    source = "wikidata, OSM"
    osm_bot_abstraction_layer.make_edit(e['osm_object_url'], comment, automatic_status, discussion_url, osm_wiki_documentation_page, type, data, source)

def change_to_local_language(e):
    if e['error_id'] != 'wikipedia tag unexpected language':
        return
    data = get_and_verify_data(e)
    if data == None:
        return None
    if is_edit_allowed_object_based_on_location(e['osm_object_url'], data, "pl", very_rough_verification_function_is_within_given_country_prefers_false_negatives) == False:
        print("Skipping object", e['osm_object_url'], "- apparently not within catchment area")
        print("ONLY EXTREMELY ROUGH CHECK WAS MADE! FALSE POSITIVES EXPECTED!")
        print("---------------------------------")
        print()
        print()
        #announce_skipping_object_as_outside_area(e['osm_object_url'])
        # TODO: what about objects exactly on borders? This could result in a slow moving edit wars...
        # Nominatim-based checking will not work reliably here...

        # TODO What about objects between "absolutely certain core" and borders?
        # right now I skip them...
        return

    # run validator check again to prevent editing based on stale data
    # ask to run check without using cached data
    # done only for objects scheduled to be deleted so some Wikimedia API is fine
    print(data['tag'])
    object_description = e['osm_object_url']
    wikipedia = data['tag']['wikipedia'] # must be present given that error is about bad Wikipedia in the first place
    wikidata = data['tag']['wikidata'] # there may be need to get it somehow
    new_report = wikimedia_link_issue_reporter.WikimediaLinkIssueDetector(forced_refresh=True).get_wikipedia_language_issues(object_description, tags, wikipedia, wikidata_id)
    if desired_wikipedia_target_from_report(e) != desired_wikipedia_target_from_report(new_report):
        print(e)
        print(new_report)
        print(desired_wikipedia_target_from_report(e))
        print(desired_wikipedia_target_from_report(new_report))
        raise Exception("report seems outdated")
    now = data['tag']['wikipedia']
    new = desired_wikipedia_target_from_report(e)
    reason = ", as wikipedia page in the local language should be preferred"
    comment = fit_wikipedia_edit_description_within_character_limit_changed(now, new, reason)
    data['tag']['wikipedia'] = new
    discussion_url = None
    #osm_wiki_documentation_page = 
    automatic_status = osm_bot_abstraction_layer.manually_reviewed_description()
    type = e['osm_object_url'].split("/")[3]
    source = "wikidata, OSM"
    osm_bot_abstraction_layer.make_edit(e['osm_object_url'], comment, automatic_status, discussion_url, osm_wiki_documentation_page, type, data, source)

def filter_reported_errors(reported_errors, matching_error_ids):
    errors_for_removal = []
    for e in reported_errors:
        if e['error_id'] in matching_error_ids:
            errors_for_removal.append(e)
    return errors_for_removal

def is_edit_allowed_object_based_on_location(osm_object_url, object_data, target_country, verification_function_is_within_given_country):
    if target_country != "pl":
        raise "unimplemented"
    print()
    for node_id in osm_bot_abstraction_layer.get_all_nodes_of_an_object(osm_object_url):
        node_data = osm_bot_abstraction_layer.get_data(node_id, "node")
        if verification_function_is_within_given_country(osm_object_url, node_data["lat"], node_data["lon"], target_country) == False:
            return False
    print()
    print(object_data)
    return True

def detailed_verification_function_is_within_given_country(root_osm_object_url, lat, lon, target_country):
    if is_location_clearly_outside_territory(lat, lon, target_country):
        return False
    if is_location_possibly_outside_territory(lat, lon, target_country):
        return check_with_nominatim_is_within_given_country(root_osm_object_url, lat, lon, target_country, debug=True)
    return True

def very_rough_verification_function_is_within_given_country_prefers_false_negatives(root_osm_object_url, lat, lon, target_country):
    if is_location_clearly_inside_territory(lat, lon, target_country) == True:
        return True
    return False

def check_with_nominatim_is_within_given_country(root_osm_object_url, lat, lon, target_country, debug):
    if debug:
        print(lat, lon, "- part of", root_osm_object_url, "was classified as possibly outside - running nominatim to check", target_country)
    if get_nominatim_country_code(lat, lon) == target_country:
        return True
    else:
        if debug:
            print(lat, lon, "- part of", root_osm_object_url, "was classified as outside", target_country)
            print(link_to_point(lat, lon))
        return False

def is_location_clearly_outside_territory(lat, lon, target_country):
    if target_country == "pl":
        if lat < 48.166:
            return True
        if lat > 55.678:
            return True
        if lon < 12.480:
            return True
        if lon > 25.137:
            return True
        return False
    raise

def is_location_clearly_inside_territory(lat, lon, target_country):
    if target_country == "pl":
        if lat >= 48.166:
            return False
        if lat <= 55.678:
            return False
        if lon >= 12.480:
            return False
        if lon <= 25.137:
            return False
        return True
    raise

def is_location_possibly_outside_territory(lat, lon, target_country):
    if target_country == "pl":
        if lat < 53.943:
            if lat > 51.069:
                if lon < 22.643:
                    if lon > 15.128:
                        return False 
    if target_country == "pl":
        if lat < 51.241:
            if lat > 49.746:
                if lon < 22.302:
                    if lon > 18.875:
                        return False
    return True

def announce_skipping_object_as_outside_area(osm_object_url):
    print("Skipping object", osm_object_url, "- apparently not within catchment area")
    print("---------------------------------")
    print()
    print()

def add_wikidata_tag_from_wikipedia_tag(reported_errors):
    errors_for_removal = filter_reported_errors(reported_errors, ['wikidata from wikipedia tag'])
    if errors_for_removal == []:
        return
    automatic_status = osm_bot_abstraction_layer.fully_automated_description()
    affected_objects_description = ""
    comment = "add wikidata tag based on wikipedia tag"
    discussion_url = 'https://forum.openstreetmap.org/viewtopic.php?id=59925'
    osm_wiki_page_url = 'https://wiki.openstreetmap.org/wiki/Mechanical_Edits/Mateusz_Konieczny_-_bot_account/adding_wikidata_tags_based_on_wikipedia_tags_in_Poland'
    api = osm_bot_abstraction_layer.get_correct_api(automatic_status, discussion_url)
    source = "wikidata, OSM"
    builder = osm_bot_abstraction_layer.ChangesetBuilder(affected_objects_description, comment, automatic_status, discussion_url, osm_wiki_page_url, source)
    started_changeset = False

    for e in errors_for_removal:
        data = get_and_verify_data(e)
        if data == None:
            continue
        if is_edit_allowed_object_based_on_location(e['osm_object_url'], data, "pl", detailed_verification_function_is_within_given_country) == False:
            announce_skipping_object_as_outside_area(e['osm_object_url'] + " (add_wikidata_tag_from_wikipedia_tag function)")
            continue

        wikipedia_tag = data['tag']['wikipedia']
        language_code = wikimedia_connection.get_language_code_from_link(wikipedia_tag)
        article_name = wikimedia_connection.get_article_name_from_link(wikipedia_tag)
        wikidata_id = wikimedia_connection.get_wikidata_object_id_from_article(language_code, article_name)

        reason = ", as wikidata tag may be added based on wikipedia tag"
        change_description = e['osm_object_url'] + " " + str(e['prerequisite']) + " to " + wikidata_id + reason
        print(change_description)
        osm_bot_abstraction_layer.sleep(2)
        data['tag']['wikidata'] = wikidata_id
        type = e['osm_object_url'].split("/")[3]
        if started_changeset == False:
            started_changeset = True
            builder.create_changeset(api)
        osm_bot_abstraction_layer.update_element(api, type, data)

    if started_changeset:
        api.ChangesetClose()
        osm_bot_abstraction_layer.sleep(60)

def add_wikipedia_tag_from_wikidata_tag(reported_errors):
    errors_for_removal = filter_reported_errors(reported_errors, ['wikipedia from wikidata tag'])
    if errors_for_removal == []:
        return
    automatic_status = osm_bot_abstraction_layer.fully_automated_description()
    affected_objects_description = ""
    comment = "add wikipedia tag based on wikidata tag"
    discussion_url = 'https://forum.openstreetmap.org/viewtopic.php?id=59888'
    osm_wiki_page_url = 'https://wiki.openstreetmap.org/wiki/Mechanical_Edits/Mateusz_Konieczny_-_bot_account/adding_wikipedia_tags_based_on_wikidata_tags_in_Poland'
    api = osm_bot_abstraction_layer.get_correct_api(automatic_status, discussion_url)
    source = "wikidata, OSM"
    builder = osm_bot_abstraction_layer.ChangesetBuilder(affected_objects_description, comment, automatic_status, discussion_url, osm_wiki_page_url, source)
    started_changeset = False

    for e in errors_for_removal:
        data = get_and_verify_data(e)
        if data == None:
            continue

        if is_edit_allowed_object_based_on_location(e['osm_object_url'], data, "pl", detailed_verification_function_is_within_given_country) == False:
            announce_skipping_object_as_outside_area(e['osm_object_url'] + " (add_wikipedia_tag_from_wikidata_tag function)")
            continue

        new = desired_wikipedia_target_from_report(e)
        reason = ", as wikipedia tag may be added based on wikidata"
        change_description = e['osm_object_url'] + " " + str(e['prerequisite']) + " to " + new + reason
        print(change_description)
        data['tag']['wikipedia'] = new
        type = e['osm_object_url'].split("/")[3]
        if started_changeset == False:
            started_changeset = True
            builder.create_changeset(api)
        osm_bot_abstraction_layer.update_element(api, type, data)

    if started_changeset:
        api.ChangesetClose()
        osm_bot_abstraction_layer.sleep(60)

def link_to_point(lat, lon):
    return "https://www.openstreetmap.org/?mlat=" + str(lat) + "&mlon=" + str(lon) + "#map=10/" + str(lat) + "/" + str(lon)

def main():
    wikimedia_connection.set_cache_location(osm_handling_config.get_wikimedia_connection_cache_location())
    connection = sqlite3.connect(config.database_filepath())
    cursor = connection.cursor()
    # for testing: api="https://api06.dev.openstreetmap.org", 
    # website at https://master.apis.dev.openstreetmap.org/
    for entry in config.get_entries_to_process():
        if entry.get('language_code', None) == "pl":
            reported_errors = load_errors(cursor, entry["internal_region_name"])
            add_wikipedia_tag_from_wikidata_tag(reported_errors)
            add_wikidata_tag_from_wikipedia_tag(reported_errors)
            for e in reported_errors:
                handle_follow_wikipedia_redirect(e)
                change_to_local_language(e)
                pass

if __name__ == '__main__':
    main()

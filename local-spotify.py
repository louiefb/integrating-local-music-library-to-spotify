import os
import re
import spotipy
import jaro
import pandas as pd
import spotipy.util as util

from collections import defaultdict
from mutagen.id3 import ID3
from mutagen.flac import FLAC

def strip_extension(file):
    pattern = r"\.[A-Za-z\d]+$"
    file = re.sub(pattern, "", file)
    return file

def has_ID(file):
    """ Checks if file has IDv3 tag. """
    try:
        ID3(file)
        return True
    except:
        try:
            FLAC(file)
            return True
        except:
            return False

def get_artist(path, track, sep):
    """ Retrieves artist from IDv3 tag, or deduces from 'artist(sep)title' filename. """
    file = os.path.join(path, track)
    if has_ID(file):
        try:
            file = ID3(file)
            if file.get("TPE1"):
                return file["TPE1"].text[0]
        except:
            file = FLAC(file)
            if file.get("artist"):
                return file["artist"][0]
    track = strip_extension(track)
    if track.count(sep) == 0:
        return str()
    else:
        return track.split(sep, maxsplit=1)[0]

def get_title(path, track, sep):
    """ Retrieves title from IDv3 tag, or deduces from 'artist(sep)title' filename. """
    file = os.path.join(path, track)
    if has_ID(file):
        try:
            file = ID3(file)
            if file.get("TIT2"):
                return file["TIT2"].text[0]
        except:
            file = FLAC(file)
            if file.get("title"):
                return file["title"][0]
    track = strip_extension(track)
    if track.count(sep) == 0:
        return track
    else:
        return track.split(sep, maxsplit=1)[1]

def get_keywords(query, type="artist"):
    """ Generates list of search terms by separating artists if type is "artist", or by tokenizing query if type is not "artist". """
    if type == "artist":
        pattern = r"[,\&]\s*|\s+feat[\.]*\s+"
        keywords = [re.sub(pattern, " ", query)]
        keywords.extend(re.split(pattern, query, flags=re.IGNORECASE))
    else:
        keywords = [query]
        keywords.extend(re.split(r"[\s\(\)]+", \
                             query, \
                             flags=re.IGNORECASE))
    keywords = list(filter(lambda keyword: keyword is not "", keywords))
    keywords = [keyword.lower().strip() for keyword in keywords]
    return keywords

def get_keys(artist, title):
    """ Generates tuple of search terms for artist and search terms for title. """
    artist_keys = get_keywords(artist, type="artist")

    title_keys = get_keywords(title, type="title")
    title_keys = sorted(title_keys, key=len, reverse=True)
    title_keys = title_keys[1:] + [title_keys[0]]

    return artist_keys, title_keys

def get_q(artist_keys, title_keys):
    """ Detailed Spotify search with artist and title tags. """

    artist_keys = '"' + '" OR "'.join(artist_keys) + '"'
    title_keys = '"' + '" OR "'.join(title_keys) + '"'

    q = f"artist:{artist_keys} track:{title_keys}"
    query = sp.search(q=q, type="track")["tracks"]["items"]
    return query

def get_q_simple(artist_keys, title_keys):
    """ Tagless, simplified Spotify search. """
    q = " ".join(artist_keys) + " " + " ".join(title_keys)
    query = sp.search(q=q, type="track")["tracks"]["items"]
    return query

def get_string_similarity(string1, string2):
    """ Uses Jaro-Winkler to calculate similarity score of two strings. """
    string1 = string1.lower()
    string2 = string2.lower()

    similarity_score = jaro.jaro_winkler_metric(string1, string2)
    return similarity_score

def get_best_match(artist, title):
    """ Retrieves Spotify track URI, artist, title, and similarity score of closest match to given artist and title. """
    """ Performs both detailed search and tagless, simplified search. """
    artist_keys, title_keys = get_keys(artist, title)
    query = get_q(artist_keys, title_keys)
    while not query and len(title_keys) > 1:
        if get_q_simple(artist_keys, title_keys):
            query = get_q_simple(artist_keys, title_keys)
            break
        title_keys = title_keys[:-1]
        query = get_q(artist_keys, title_keys)

    if query:
        best_match = defaultdict(list)
        for idx in range(len(query)):
            artists_found = query[idx]["artists"]
            artists_found = [artists_found[i]["name"] for i in range(len(artists_found))]
            artists_found = " ".join(artists_found)
            best_match["artist"].append(artists_found)

            title_found = query[idx]["name"]
            best_match["title"].append(title_found)

            best_match["uri"].append(query[idx]["uri"])

            score = get_string_similarity(artists_found + title_found, artist + title)

            best_match["id"].append(idx)
            best_match["score"].append(score)

    else:
        print(f"No matches for {artist} - {title}.\n")
        return "", "", "", 0

    best_match_idx = max(best_match["score"])
    best_match_idx = best_match["score"].index(best_match_idx)

    best_match_artist = best_match["artist"][best_match_idx]
    best_match_title = best_match["title"][best_match_idx]
    best_match_uri = best_match["uri"][best_match_idx]
    best_match_score = best_match["score"][best_match_idx]

    return best_match_artist, best_match_title, best_match_uri, best_match_score

def extract_local_files(path, sep=" - ", *filetypes):
    """ Extracts information of all immediate files in the given path and outputs to df. """
    """ Uses IDv3 tags when possible, otherwise uses filename to deduce 'artist(sep)title'. """
    filetypes = [filetype.lower() for filetype in filetypes]
    
    if os.path.isdir(path) is False:
        raise ValueError(f"{path} is not a valid directory")
    files = os.listdir(path)
    files = list(filter(lambda file: os.path.isfile(os.path.join(path, file)), files))
    files = list(filter(lambda file: any([file.lower().endswith(filetype) for filetype in filetypes]), files))

    m_time = (os.path.getmtime(os.path.join(path, file)) for file in files)

    df = pd.DataFrame(list(zip(m_time, files)))
    df.columns = ["time", "filename"]
    
    df = df.sort_values("time")
    df.reset_index(drop=True, inplace=True)

    df["local_artist"] = df["filename"].apply(lambda row: get_artist(path, row, sep))
    df["local_title"] = df["filename"].apply(lambda row: get_title(path, row, sep))

    return df

def scrape_spotify(df):
    """ Identifies Spotify track URI, artist, title, and similarity score of closest match to every track of df. """
    scrape = lambda row: get_best_match(row["local_artist"], row["local_title"])
    scraped_df = df.apply(scrape, axis=1)
    scraped_df = pd.DataFrame(scraped_df.tolist())

    df["artists"] = scraped_df.iloc[:, 0]
    df["title"] = scraped_df.iloc[:, 1]
    df["uri"] = scraped_df.iloc[:, 2]
    df["score"] = scraped_df.iloc[:, 3]

    return df

def add_tracks(df, playlist_uri, threshold):
    """ Add df of tracks to playlist according to modified date. """
    for row in df.itertuples():
        if row.uri and (row.score > threshold):
            sp.user_playlist_add_tracks(user, playlist_uri, [row.uri])
        else:
            input(f"Please add {row.local_artist} - {row.local_title} manually then hit Return key to proceed.\n")

def add_to_playlist(df, threshold=0.5):
    """ Add df of tracks to existing playlist. """
    playlists = sp.user_playlists(user)
    user_playlists = []

    print("Enter index of playlist:")
    while playlists:
        for idx, playlist in enumerate(playlists['items']):
            user_playlists.append(playlist["uri"])
            print(f'{idx} - {playlist["name"]}')
        if playlists["next"]:
            playlists = sp.next(playlists)
        else:
            playlists = None
    selection = input("")

    if selection.isnumeric():
        selection = int(selection)
    else:
        raise TypeError(f"Index must be an integer")
    if selection < len(user_playlists):
        playlist_uri = user_playlists[selection]
        add_tracks(df, playlist_uri, threshold)
    else:
        raise TypeError(f"Index is out of range")

def generate_playlist(df, playlist_name, threshold=0.5):
    """ Generates new playlist from df of tracks. """
    new_playlist = sp.user_playlist_create(user, playlist_name)

    add_tracks(df, new_playlist["uri"], threshold)

#local source folder
path = r"\Music"

#credentials
user = "yourusername"
cid = "9d3d4ea8e8bc4e6db7fc82bf2a7f91cc"
secret = "**********"
scope = "playlist-modify-public"
redirect = r"http://127.0.0.1:9090"
token = util.prompt_for_user_token(user, scope, \
                                   client_id=cid, \
                                   client_secret=secret, \
                                   redirect_uri=redirect)
sp = spotipy.Spotify(auth=token)

#add to existing playlist
df = extract_local_files(path, " - ", "MP3", "flac")
df = scrape_spotify(df)
add_to_playlist(df, threshold=0.6)

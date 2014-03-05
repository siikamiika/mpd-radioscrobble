#!/usr/bin/env python3
import socket
import time
import sys
import pylast
from datetime import datetime
from html.parser import HTMLParser
hp = HTMLParser()

try:
    with open('apikey.secret', 'r') as apikey:
        API_KEY, API_SECRET = apikey.read().splitlines()[:2]
    with open('login.secret', 'r') as login:
        USERNAME, PASSWORD_HASH = login.read().splitlines()[:2]
except Exception as e:
    print(e)
    sys.exit()

def auth():
    return pylast.LastFMNetwork(
        api_key = API_KEY,
        api_secret = API_SECRET,
        username = USERNAME,
        password_hash = PASSWORD_HASH
    )

def connect():
    """Return a new connection to MPD or None on error."""
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        conn.connect(('localhost', 6600))
        print(conn.recv(1024).decode())
        return conn
    except Exception as e:
        print(e)
        return

def currentsong(connection):
    """
    Return dictionary containing MPD currentsong output.
    If no Artist is specified, try to find it from Title before ' - '.
    If Artist is not found, return -1 (meaning "skip this").
    """
    try:
        connection.send(b'currentsong\n')
        response = connection.recv(1024)
        song_dict = dict(
                (l.split(': ', 1))
                for l in response.decode().strip().splitlines()[:-1]
            )

        song_dict['timestamp'] = int(time.time())
        if not song_dict.get('Artist'):
            if ' - ' in str(song_dict.get('Title')):
                song_dict['Artist'], song_dict['Title'] = \
                    song_dict.get('Title').split(' - ', 1)
            else:
                return -1

        return song_dict

    except Exception as e:
        print(e)
        return

def scrobble(scrobbler, track):
    """
    Attempt to scrobble a track if it has non-empty Artist and Title
    keys. If the scrobble fails, try to reauthenticate and scrobble
    the track one more time. If that scrobble succeeds, the new
    authentication is passed to the loop for future use. Otherwise
    the scrobbler will exit with an error.
    """
    if not (track['Artist'] and track['Title']):
        return
    track_args = dict(
            # Unescape artist and title just in case
            artist=hp.unescape(track['Artist']),
            title=hp.unescape(track['Title']),
            album=track.get('Album'),
            album_artist=track.get('AlbumArtist'),
            duration=track.get('Time'),
            track_number=track['Track'].split('/')[0] if track.get('Track')
                         else None,
            timestamp=track['timestamp']
        )
    scrobble_info = '{0} scrobbled: {1} - {2}'.format(
            datetime.now().replace(microsecond=0),
            track['Artist'], track['Title']
        )
    try:
        scrobbler.scrobble(**track_args)
        print(scrobble_info)
    except Exception as e:
        print('{}, attempting reauth...'.format(e))
        scrobbler = auth()
        scrobbler.scrobble(**track_args)
        print(scrobble_info)
        return scrobbler

def publish_nowplaying(scrobbler, scrobblequeue):
    try:
        scrobbler.update_now_playing(
            scrobblequeue.get('Artist'), queue.get('Title')
        )
    except Exception as e:
        print('can\'t publish nowplaying:', e)


def is_new_track(queue, submittable):
    """Triggers the scrobble of a queued track when True"""
    if not queue:
        queue = dict()
    queue['timestamp'] = None
    submittable['timestamp'] = None
    if queue.items() - submittable.items():
        return True
    else:
        return False


if __name__ == '__main__':
    # prepare for loop
    conn = connect()
    queue = currentsong(conn)
    scrobbler = auth()
    publish_nowplaying(scrobbler, queue)

    # check currentsong every 10 sec
    while True:
        submittable = currentsong(conn)
        if not submittable:
            conn = connect()
            # if mpd is closed, wait 60 sec and try reconnect
            if not conn:
                time.sleep(60)
                continue
            else:
                submittable = currentsong(conn)

        # ignore invalid songs
        elif submittable == -1:
                pass

        # scrobble queued track, check authentication, update queue
        # and publish current song with update_now_playing
        elif is_new_track(dict(queue), dict(submittable)):
            reauth = scrobble(scrobbler, queue)
            if reauth:
                scrobbler = reauth
            queue = dict(submittable)
            publish_nowplaying(scrobbler, queue)

        time.sleep(10)

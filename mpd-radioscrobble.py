#!/usr/bin/env python3
import socket
import time
import sys
import os
from traceback import print_exc
import re
import pylast
from threading import Thread
from datetime import datetime
from html.parser import HTMLParser
hp = HTMLParser()

DEBUG = False

try:
    with open('apikey.secret', 'r') as apikey:
        API_KEY, API_SECRET = apikey.read().splitlines()[:2]
    with open('login.secret', 'r') as login:
        USERNAME, PASSWORD_HASH = login.read().splitlines()[:2]
except Exception as e:
    print_exc()
    sys.exit()

def auth():
    return pylast.LastFMNetwork(
        api_key = API_KEY,
        api_secret = API_SECRET,
        username = USERNAME,
        password_hash = PASSWORD_HASH
    )

def keybind_listener():
    """
    xbindkeys can be used to echo commands to the fifo
    example .xbindkeysrc entry:
    "echo love > /tmp/scrobbler.fifo"
        Control+Alt + KP_Insert
    """
    fifo_path = '/tmp/scrobbler.fifo'
    if os.path.exists(fifo_path):
        os.remove(fifo_path)
    os.mkfifo(fifo_path)
    playback_commands = re.compile(
        '^(next|previous|play|stop|volume (\+|-)[0-9]{1,2})$')
    global SCROBBLING
    while True:
        with open(fifo_path, 'r') as f:
            try:
                command = f.read().splitlines()[0]
                if command == 'SCROBBLING':
                    SCROBBLING = not SCROBBLING
                    print('scrobbling: {}'.format(SCROBBLING))
                # love or unlove current song on last.fm
                elif command in ['love', 'unlove']:
                    print(command, queue['Title'])
                    scrobbler.get_track(
                        artist=queue['Artist'],
                        title=queue['Title']
                        )._request('track.{}'.format(command))
                # if stopped, send play instead of pause
                elif command == 'pause':
                    conn.send(b'status\n')
                    if b'state: stop' in conn.recv(1024):
                        conn.send(b'play\n')
                    else:
                        conn.send((command+'\n').encode())
                    conn.recv(1024)
                # other MPD playback commands
                elif playback_commands.match(command):
                    conn.send((command+'\n').encode())
                    conn.recv(1024)
                else:
                    print('unknown command:', command)
            except Exception as e:
                print_exc()

def connect():
    """Return a new connection to MPD or None on error."""
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        conn.connect(('localhost', 6600))
        print(conn.recv(1024).decode())
        return conn
    except Exception as e:
        print_exc()
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
        print_exc()
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
        #debug = \
        scrobbler.scrobble(**track_args)
        print(scrobble_info)
        #if debug:
        #    print('scrobble debug:\n', debug.toprettyxml())
    except Exception as e:
        print('{}, attempting reauth...'.format(e))
        scrobbler = auth()
        scrobbler.scrobble(**track_args)
        print(scrobble_info)
        return scrobbler

def publish_nowplaying(scrobbler, scrobblequeue):

    if DEBUG:
        def debug_now_playing(self, artist, title):
            params = {'track': title, 'artist': artist}
            return pylast._Request(
                self, 'track.updateNowPlaying', params
            ).execute()

        scrobbler.update_now_playing = debug_now_playing.__get__(
            scrobbler, pylast.LastFMNetwork
        )

    try:
        debug = scrobbler.update_now_playing(
            scrobblequeue.get('Artist'), queue.get('Title')
        )
        if debug:
            print('nowplaying debug:\n', debug.toprettyxml())
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
    SCROBBLING = True
    conn = connect()
    queue = currentsong(conn)
    scrobbler = auth()
    publish_nowplaying(scrobbler, queue)
    Thread(target=keybind_listener).start()

    # check currentsong every 10 sec
    while True:
        if not SCROBBLING:
            queue = -1
            time.sleep(10)
            continue
        submittable = currentsong(conn)
        if not submittable:
            conn = connect()
            # if mpd is closed, wait 60 sec and try reconnect
            if not conn:
                time.sleep(60)
                continue

        # ignore invalid songs
        elif submittable == -1:
            pass

        # fix for invalid first track
        elif queue == -1:
            queue = dict(submittable)

        # scrobble queued track, check authentication, update queue
        # and publish current song with update_now_playing
        elif is_new_track(dict(queue), dict(submittable)):
            reauth = scrobble(scrobbler, queue)
            if reauth:
                scrobbler = reauth
            queue = dict(submittable)
            time.sleep(1)
            publish_nowplaying(scrobbler, queue)

        time.sleep(10)

mpd-radioscrobble
=================

Compatibility
-------------
Works with python 3.3 on linux

Required external libraries
---------------------------
pylast

License
-------
Whatever pylast license (Apache 2.0) allows if that even matters

Howto
-----
Place apikey.secret and login.secret in the
directory where you run mpd_radioscrobble.py.

login.secret has your username and password hash
separated with a newline, such as:

	username123
	bed128365216c019988915ed3add75fb

Run [password-hash.py](password-hash.py) to generate
login.secret with your username and password hash.

For apikey.secret you need an account from
http://www.last.fm/api/account/create
which provides two random values: API Key and Secret.
They will be in apikey.secret like this:

	1deffca257db653419a4aeeebdf479c8
	686acd26c21ceca33901d80107a81e20

Known features
--------------
Rearranging playlist will cause random scrobbles
because it changes "Id" in "currentsong" output.
To be able to scrobble a local track multiple times
in a row you can't ignore "Id".

When MPD is paused, the previous track will be scrobbled
the next time a track changes.


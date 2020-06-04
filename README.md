# integrating-local-music-library-to-spotify
API for integrating local music files to Spotify playlists using ID tag or filename pattern matching

### Background ###
As of late May 2020, per **Spotify** documentation, "*it is not currently possible to add local files to playlists using the Web API...*". The best alternative therefore is to use the Web API to query the available equivalent tracks of local files and add those to a new or existing playlist. When no equivalent is available, the user is prompted to add the local files to the playlist manually, or skip the missing tracks.

### Usage ###
Tracks are fetched by supplying the source folder. The *artist* and *title* are queried from the ID tags (MP3 and FLAC audio files are supported). If no tags are available, the artist-track parsing is done at the the filename level by indicating the delimiter (*sep*). These information are used to perform a detailed search request to the Web API and the best-match track is retrieved. The tracks are scored using string-similarity &ndash; *Spotify's artists and title vs. local tag's artists and title* &ndash; and the user identifies the accept-fail score threshold. 

All information (including filename, artist tag, title tag, equivalent Spotify track, Spotify URI, similarity score, etc.) are stored in a Pandas dataframe. User is free to review, update, or delete entries before appending the tracks to a new or existing playlist.

Please refer to the `API Reference Guide.ipynb` for examples and more details.

### Dependencies ###
1. *Spotipy*, the Spotify Web API wrapper for Python
2. *Pandas*, for organizing library and data onto dataframes
3. *Mutagen*, for reading IDv3 tags of MP3 and FLAC files
4. *Jaro*, for the Jaro-Winkler string-similarity scoring algorithm

Louie Balderrama
https://www.linkedin.com/in/marioluisbalderrama/

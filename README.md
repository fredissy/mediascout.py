# Mediascout - Media Cover Manager

A companion web application for minidlna to automatically find and download movie cover artwork from The Movie Database (TMDB).

## Features

- 🎬 Automatic scanning of media directories
- 🔍 Smart movie title extraction from filenames
- 🎨 TMDB API integration for cover artwork
- 📐 Automatic image resizing to 160x160 JPEG
- 🎯 Interactive cover selection interface
- 📱 Responsive, professional design

## Installation

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

2. **Get a TMDB API key:**
   - Sign up at https://www.themoviedb.org/
   - Go to Settings → API
   - Request an API key (free)

3. **Configure the application:**

**Option A: Environment variables**
```bash
export MEDIA_DIRECTORIES="/media/movies,/mnt/films"
export FILE_EXTENSIONS="mkv,mp4,avi"
export TMDB_API_KEY="your_api_key_here"
```

**Option B: Command line arguments**
```bash
python app.py \
  --directories "/media/movies,/mnt/films" \
  --extensions "mkv,mp4,avi" \
  --tmdb-key "your_api_key_here"
```

## Usage

1. **Start the application:**
```bash
python app.py
```

2. **Open your browser:**
```
http://localhost:8000
```

3. **Workflow:**
   - View all configured directories on the home page
   - Click a directory to scan for movies without covers
   - Review TMDB matches and select covers
   - Click "Download Selected Covers" to save them

## Project Structure

```
mediascout/
├── app.py                 # Main application
├── requirements.txt       # Python dependencies
├── templates/
│   ├── base.html         # Base template
│   ├── index.html        # Directory listing page
│   └── scan.html         # Movie selection page
└── README.md
```

## Configuration Options

| Option | Environment Variable | CLI Argument | Description |
|--------|---------------------|--------------|-------------|
| Directories | `MEDIA_DIRECTORIES` | `--directories` | Comma-separated list of media directories |
| Extensions | `FILE_EXTENSIONS` | `--extensions` | Comma-separated list of file extensions (mkv,mp4,avi) |
| TMDB Key | `TMDB_API_KEY` | `--tmdb-key` | Your TMDB API key |
| Port | - | `--port` | Server port (default: 8000) |
| Host | - | `--host` | Server host (default: 0.0.0.0) |

## Filename Parsing

The app intelligently extracts movie titles from various filename formats:

- `The.Matrix.1999.1080p.BluRay.x264.mkv` → "The Matrix" (1999)
- `The Matrix.mkv` → "The Matrix"
- `2012.mkv` → "2012" (handles movies with years as titles)
- `Blade Runner 2049.mkv` → "Blade Runner 2049" (keeps year in title)

## Cover File Format

- **Size:** 160x160 pixels
- **Format:** JPEG (90% quality)
- **Naming:** Same as movie file with `.jpg` extension
  - Example: `The.Matrix.1999.mkv` → `The.Matrix.1999.jpg`

## Requirements

- Python 3.8 or higher
- Internet connection (for TMDB API)
- Read/write access to media directories

## Troubleshooting

**"No results found" for a movie:**
- Check if the filename is clear enough to parse
- Try manually searching TMDB to verify the movie exists
- The year in the filename helps narrow results

**Permission errors:**
- Ensure the application has write access to media directories
- Check file/folder permissions

**TMDB API errors:**
- Verify your API key is correct
- Check TMDB API status at status.themoviedb.org
- Respect rate limits (40 requests per 10 seconds)

## License

Built for personal use with minidlna.

## Credits

- Movie data provided by The Movie Database (TMDB)
- Built with Flask and Python
# Eureka Backend Services

This project consists of two separate backend services designed to support the Eureka learning platform.

## Architecture

1. **AI Backend (`ai_backend/`)**
   - **Service**: Flask API
   - **Port**: 8000
   - **Responsibilities**: 
     - Generating courses and questions using LLMs.
     - Managing user profiles and learning progress.
     - Providing a "Debug Coach" for interactive coding assistance.
     - Running code snippets and validating tests.

2. **Face Recognition Backend (`face_backend/`)**
   - **Service**: Flask API
   - **Port**: 5001
   - **Responsibilities**:
     - Real-time face tracking and focus detection using MediaPipe.
     - Providing a video stream of processed frames.
     - Reporting focus status (FOCUSED, NOT FOCUSED - SIDE, NOT FOCUSED - DOWN).

## Getting Started

### Prerequisites

- Python 3.10+
- `uv` (recommended for dependency management)

### Installation

Install dependencies:
```bash
uv pip install -e .
```

### Running the Services

Use the provided startup script to launch both backends simultaneously:
```bash
./start.sh
```

The script will:
- Launch the AI Backend on `http://localhost:8000`
- Launch the Face Recognition Backend on `http://localhost:5001`
- Log output to `ai_backend.log` and `face_backend.log`

### API Endpoints

#### AI Backend
- `POST /api/ai/generate-course`: Generate a full course based on a topic.
- `POST /api/ai/qa`: Ask a coding question.
- `POST /api/ai/debug-coach`: Get debugging help for code.
- `GET /user-state`: Retrieve current user progress and recommendations.

#### Face Recognition Backend
- `GET /status`: Get the current focus status (string).
- `GET /video`: Stream the processed camera feed.

## Cleanup

To stop the services, press `Ctrl+C` in the terminal where `start.sh` is running.

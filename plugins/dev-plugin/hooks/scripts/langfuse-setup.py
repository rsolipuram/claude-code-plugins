#!/usr/bin/env python3
"""
Background Langfuse setup script.
Runs asynchronously to set up complete Langfuse environment.

Responsibilities:
- Check/install Langfuse Docker setup
- Install Python SDK dependencies
- Start Docker Compose
- Wait for health check
- Log all progress
"""

import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path


class LangfuseSetup:
    """Handles full Langfuse environment setup."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.log_file = project_dir / '.claude' / 'observability' / 'setup.log'
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str) -> None:
        """Log message to file."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_file, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")

    def setup(self) -> bool:
        """Run complete setup process."""
        self.log("="*60)
        self.log("Starting Langfuse setup")
        self.log("="*60)

        try:
            # Step 1: Check/install Langfuse
            if not self.check_langfuse_installed():
                self.log("Langfuse not found, installing...")
                if not self.install_langfuse():
                    self.log("ERROR: Failed to install Langfuse")
                    return False
            else:
                self.log("Langfuse already installed ✓")

            # Step 2: Check/install dependencies
            if not self.check_dependencies():
                self.log("Installing Python dependencies...")
                if not self.install_dependencies():
                    self.log("ERROR: Failed to install dependencies")
                    return False
            else:
                self.log("Dependencies already installed ✓")

            # Step 3: Start Docker
            if not self.is_docker_running():
                self.log("Starting Docker Compose...")
                if not self.start_docker():
                    self.log("ERROR: Failed to start Docker")
                    return False
            else:
                self.log("Docker already running ✓")

            # Step 4: Wait for health check
            self.log("Waiting for Langfuse to be healthy...")
            if not self.wait_for_health():
                self.log("ERROR: Langfuse health check failed")
                return False

            self.log("="*60)
            self.log("✓ Langfuse setup complete!")
            self.log("="*60)
            return True

        except Exception as e:
            self.log(f"ERROR: Setup failed: {str(e)}")
            return False

    def check_langfuse_installed(self) -> bool:
        """Check if Langfuse Docker setup exists."""
        langfuse_paths = [
            Path.home() / 'langfuse-docker' / 'docker-compose.yml',
            Path.home() / '.langfuse' / 'docker-compose.yml',
        ]

        for path in langfuse_paths:
            if path.exists():
                self.langfuse_dir = path.parent
                return True

        return False

    def install_langfuse(self) -> bool:
        """Install Langfuse by cloning repository."""
        try:
            langfuse_dir = Path.home() / 'langfuse-docker'

            # Clone Langfuse repo
            result = subprocess.run(
                ['git', 'clone', 'https://github.com/langfuse/langfuse.git', str(langfuse_dir)],
                capture_output=True,
                timeout=120
            )

            if result.returncode == 0:
                self.langfuse_dir = langfuse_dir
                self.log(f"Cloned Langfuse to {langfuse_dir}")

                # Create .env with secure defaults
                env_file = langfuse_dir / '.env'
                if not env_file.exists():
                    self.create_env_file(env_file)

                return True
            else:
                self.log(f"Git clone failed: {result.stderr.decode()}")
                return False

        except Exception as e:
            self.log(f"Install failed: {str(e)}")
            return False

    def create_env_file(self, env_file: Path) -> None:
        """Create .env file with secure defaults."""
        import secrets

        env_content = f"""# Auto-generated Langfuse configuration
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET={secrets.token_hex(32)}
SALT={secrets.token_hex(16)}
ENCRYPTION_KEY={secrets.token_hex(32)}

# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD={secrets.token_hex(20)}
DATABASE_URL=postgresql://postgres:{secrets.token_hex(20)}@postgres:5432/postgres

# ClickHouse
CLICKHOUSE_USER=clickhouse
CLICKHOUSE_PASSWORD={secrets.token_hex(20)}

# Redis
REDIS_AUTH={secrets.token_hex(20)}

# MinIO
MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD={secrets.token_hex(20)}
"""

        env_file.write_text(env_content)
        self.log("Created .env file with secure defaults")

    def check_dependencies(self) -> bool:
        """Check if langfuse SDK is installed."""
        try:
            import langfuse
            return True
        except ImportError:
            return False

    def install_dependencies(self) -> bool:
        """Install langfuse SDK."""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'install', 'langfuse'],
                capture_output=True,
                timeout=120
            )

            if result.returncode == 0:
                self.log("Installed langfuse SDK ✓")
                return True
            else:
                self.log(f"Pip install failed: {result.stderr.decode()}")
                return False

        except Exception as e:
            self.log(f"Dependency install failed: {str(e)}")
            return False

    def is_docker_running(self) -> bool:
        """Check if Langfuse Docker containers are running."""
        try:
            # Check health endpoint
            req = urllib.request.Request('http://localhost:3000/api/public/health', method='GET')
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def start_docker(self) -> bool:
        """Start Docker Compose."""
        if not hasattr(self, 'langfuse_dir'):
            self.log("ERROR: Langfuse directory not set")
            return False

        try:
            compose_file = self.langfuse_dir / 'docker-compose.yml'
            if not compose_file.exists():
                self.log(f"ERROR: docker-compose.yml not found at {compose_file}")
                return False

            result = subprocess.run(
                ['docker-compose', 'up', '-d'],
                cwd=self.langfuse_dir,
                capture_output=True,
                timeout=120
            )

            if result.returncode == 0:
                self.log("Docker Compose started ✓")
                return True
            else:
                self.log(f"Docker Compose failed: {result.stderr.decode()}")
                return False

        except Exception as e:
            self.log(f"Docker start failed: {str(e)}")
            return False

    def wait_for_health(self, max_attempts: int = 60, delay: int = 5) -> bool:
        """Wait for Langfuse to be healthy (up to 5 minutes)."""
        for attempt in range(max_attempts):
            try:
                req = urllib.request.Request('http://localhost:3000/api/public/health', method='GET')
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        self.log(f"Health check passed after {attempt * delay}s ✓")
                        return True
            except Exception:
                pass

            if attempt % 6 == 0:  # Log every 30s
                self.log(f"Waiting for health check... ({attempt * delay}s)")

            time.sleep(delay)

        self.log("Health check timed out after 5 minutes")
        return False


def main():
    """Main execution."""
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))

    setup = LangfuseSetup(project_dir)
    success = setup.setup()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

"""Main entry point for ETB-project."""

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Main function."""
    logger.info("Starting ETB-project")
    # Add your application logic here
    logger.info("Application started successfully")


if __name__ == "__main__":
    main()


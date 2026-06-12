def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run end-to-end smoke tests that hit live vendor APIs",
    )

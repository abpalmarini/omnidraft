from fbs_runtime.application_context.PySide6 import ApplicationContext

import sys

from main_window import MainWindow


if __name__ == '__main__':
    appctxt = ApplicationContext()

    main_window = MainWindow(appctxt)
    main_window.resize(1600, 800)
    main_window.show()

    exit_code = appctxt.app.exec()
    sys.exit(exit_code)

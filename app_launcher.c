#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void trim_directory(char *path) {
    char *slash = strrchr(path, '/');
    if (slash != NULL) {
        *slash = '\0';
    }
}

int main(void) {
    char raw_executable[PATH_MAX];
    char executable[PATH_MAX];
    uint32_t size = sizeof(raw_executable);
    if (_NSGetExecutablePath(raw_executable, &size) != 0 || realpath(raw_executable, executable) == NULL) {
        return 1;
    }

    // .../Codex Scheduler.app/Contents/MacOS/CodexScheduler -> project root.
    trim_directory(executable);
    trim_directory(executable);
    trim_directory(executable);
    trim_directory(executable);

    char script[PATH_MAX];
    if (snprintf(script, sizeof(script), "%s/codex_scheduler_gui.py", executable) >= (int)sizeof(script)) {
        return 1;
    }

    const char *python_candidates[] = {
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/Library/Frameworks/Python.framework/Versions/Current/bin/python3",
        "/usr/bin/python3",
        NULL,
    };
    for (const char **python = python_candidates; *python != NULL; ++python) {
        if (access(*python, X_OK) == 0) {
            if (getenv("CODEX_SCHEDULER_SELF_TEST") != NULL) {
                execl(*python, *python, script, "--self-test", (char *)NULL);
            }
            execl(*python, *python, script, (char *)NULL);
            return 1;
        }
    }

    execl("/usr/bin/osascript", "osascript", "-e",
          "display alert \"Codex Scheduler 需要 Python 3\" message \"请先安装 Python 3，然后重新打开这个 App。\"",
          (char *)NULL);
    return 1;
}

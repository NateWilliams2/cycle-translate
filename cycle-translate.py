import http.client
import os, sys, traceback
import json
import random
import argparse
import shutil
import queue
from readchar import readkey, key
from threading import Thread, Event
from google.cloud import translate_v2 as translate


def main():
    # Initial setup
    setup = init()
    original_text = setup[0]
    max_iterations = setup[1]
    lang_set = setup[2]
    key = setup[3]
    index = 0
    q = queue.Queue(10000)
    translations: Translation = []
    running = Event()
    live = True

    # Thread for translation API calls
    t1 = Thread(
        target=cycle_translate,
        args=(running, original_text, max_iterations, lang_set, key, q),
    )
    # Thread for monitoring keyboard input
    t2 = Thread(target=monitor_keyboard, args=([q]))

    try:
        running.set()
        t1.start()
        t2.start()
        while True:
            update = q.get()
            if update == False:
                print("Shutdown requested...exiting")
                running.clear()
                t1.join()
                t2.join()
                sys.exit(0)
            elif isinstance(update, Translation):  # New translation
                translations.append(update)
                if live:
                    index = len(translations)
            elif isinstance(update, int):  # Update index
                live = False
                index = index + update
                if index < 0:
                    index = 0
            elif update == "reset":  # Reset index
                live = True
                index = len(translations)
            elif update == "print":  # Print output to file
                file_count = 0
                while os.path.isfile("output" + str(file_count) + ".txt"):
                    file_count += 1

                output = open("output" + str(file_count) + ".txt", "w")
                output.truncate(0)
                output.writelines(["Original text:\n", original_text + "\n"])
                for i, translation in enumerate(translations):
                    output.writelines(
                        [
                            "Iteration "
                            + str(i)
                            + ": "
                            + translation.target.name
                            + "\n",
                            translation.text + "\n",
                        ]
                    )
                print(
                    "Wrote translations to output"
                    + str(file_count)
                    + ".txt, exiting program..."
                )
                running.clear()
                t1.join()
                t2.join()
                sys.exit(0)
            else:
                print("unknown queue update")
                print(update)
            print_page(original_text, translations, index, max_iterations)
    except KeyboardInterrupt:
        print("Next time use 'q' or 'esc' to exit")
    except Exception:
        traceback.print_exc(file=sys.stdout)
    sys.exit(0)


def init():
    # Arguments
    parser = argparse.ArgumentParser(description="Cycle translator")
    parser.add_argument(
        "-t",
        "--text",
        type=str,
        help="The text to be translated.",
        default="I am very sad that it's going to rain tomorrow night. I was planning on going to the studio to do ceramics.",
    )
    parser.add_argument(
        "-i", "--iterations", type=int, help="The number of iterations.", default=200
    )
    parser.add_argument(
        "-k",
        "--key",
        type=str,
        help="The translate API key.",
    )
    args = parser.parse_args()

    key: str = ""
    keyfile = "./key"
    if args.key != None:
        print(args.key)
        key = args.key
        file = open(keyfile, "w")
        file.truncate(0)
        file.write(key)
    elif os.path.isfile(keyfile):
        file = open(keyfile, "r")
        key = file.readline()
    else:
        print("need to provide a google translate API key")
        sys.exit(0)

    # API setup
    connection = http.client.HTTPSConnection("translation.googleapis.com")
    connection.request("GET", "/language/translate/v2/languages?target=en&key=" + key)
    response = connection.getresponse()
    if response.status != 200:
        print("bad response from API")
        print(response.getcode())
        print(response.read().decode())
        sys.exit(0)
    langs = response.read().decode()
    languages = json.loads(langs)
    lang_set = []
    for language in languages["data"]["languages"]:
        if language.get("language") == "en":
            continue
        if language.get("language") == "pa-Arab":
            continue

        lang_set.append(Language(language.get("language"), language.get("name")))
    return args.text, args.iterations, lang_set, key


def monitor_keyboard(queue: queue.Queue):
    while True:
        ch = readkey()
        if ch == key.ESC or ch == "q":
            queue.put(False)
            return
        elif ch == key.UP:
            queue.put(-1)
        elif ch == key.DOWN:
            queue.put(1)
        elif ch == key.ENTER:
            queue.put("reset")
        elif ch == "p":
            queue.put("print")
            return


def cycle_translate(
    running: Event, orig_text, num_iterations, lang_set, api_key, queue: queue.Queue
):
    english = Language("en", "English")
    headers = {"Content-type": "application/json"}
    target = english
    text = orig_text
    for x in range(num_iterations):
        if not running.is_set():
            return
        target = random.choice(lang_set)
        translation = translate(
            headers, english.language, target.language, text, api_key
        )
        text = translate(
            headers, target.language, english.language, translation, api_key
        )
        queue.put(Translation(english, target, text, x))


def translate(headers, source, target, text, api_key):
    foo = {"q": [text], "source": source, "target": target, "format": "text"}
    json_data = json.dumps(foo)
    connection = http.client.HTTPSConnection("translation.googleapis.com")
    connection.request(
        "POST", "/language/translate/v2?key=" + api_key, json_data, headers
    )
    response = connection.getresponse()
    resp = json.loads(response.read().decode())
    if resp.get("data"):
        text = resp.get("data").get("translations")[0]["translatedText"]
    else:
        print(resp)
    return text


def print_page(original_text, translations, i, max_iterations):
    if i == None or i >= len(translations):
        i = len(translations) - 1
    os.system("cls" if os.name == "nt" else "clear")
    print_msg_box(original_text, title="Original Text")
    if len(translations) > 0:
        print(center_string("|"))
        print(center_string("|"))
        print(center_string("|"))
        print(center_string("v"))
        print(center_string(translations[i].target.name))
        print(center_string("|"))
        print(center_string("|"))
        print(center_string("|"))
        print(center_string("v"))
        print_msg_box(translations[i].text, title="Iteration " + str(i + 1))
        print("\n\n")
        print(
            center_string(
                str(len(translations))
                + " out of "
                + str(max_iterations)
                + " translation cycles completed. Press ENTER to see the latest one."
            )
        )
        print(
            center_string(
                "use the up and down arrows to scroll through the translation history."
            )
        )
        print(center_string("press 'q' or 'esc' to exit."))
        print(
            center_string(
                "press 'p' to print the translation history to output.txt and exit the program."
            )
        )


# adapted from https://stackoverflow.com/questions/39969064/how-to-print-a-message-box-in-python
def print_msg_box(msg, indent=1, width=None, title=None):
    cols = shutil.get_terminal_size((80, 20)).columns
    max_line_len = cols - 30
    msg_len = len(msg)
    lines = []
    while msg_len > 0:
        end_idx = max_line_len
        # Walk back to find a space
        while (end_idx < len(msg)) and (msg[end_idx] != " "):
            end_idx = end_idx - 1
        lines.append(msg[:end_idx])
        msg = msg[end_idx + 1 :]
        msg_len = msg_len - end_idx
    space = " " * indent
    if not width:
        width = max(map(len, lines))
    print(center_string(f'╔{"═" * (width + indent * 2)}╗'))  # upper_border
    if title:
        print(center_string(f"║{space}{title:^{width}}{space}║"))  # title
        print(
            center_string(f'║{space}{"-" * len(title):^{width}}{space}║')
        )  # underscore
    for line in lines:
        print(center_string(f"║{space}{line:<{width}}{space}║"))
    print(center_string(f'╚{"═" * (width + indent * 2)}╝'))  # lower_border)


def center_string(string):
    cols = shutil.get_terminal_size((80, 20)).columns
    return string.center(cols)


class Translation:
    def __init__(self, source, target, text, iteration):
        self.source = source
        self.target = target
        self.text = text
        self.iteration = iteration


class Language:
    def __init__(self, language, name):
        self.language = language
        self.name = name


if __name__ == "__main__":
    main()

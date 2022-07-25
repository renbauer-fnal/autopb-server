from flask import Flask, request, render_template, url_for, flash, redirect
import os
import re

# def create_app(logs=None):
#     app = Flask(__name__)
#     if not logs:
#         stream = os.popen('whoami')
#         logs = f'/home/{stream.read().strip()}/typescript'
#     app.config["logs"] = logs

app = Flask(__name__)
app.config['SECRET_KEY'] = 'df0331cefc6c2b9a5d0208a726a5d1c0fd37324feba25506'

messages = [{'title': 'Message One',
             'content': 'Message One Content'},
            {'title': 'Message Two',
             'content': 'Message Two Content'}
            ]

@app.route('/')
def index():
    return render_template('index.html', messages=messages)

@app.route('/create/', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        if not title:
            flash('Title is required!')
        elif not content:
            flash('Content is required!')
        else:
            messages.append({'title': title, 'content': content})
            return redirect(url_for('index'))

    return render_template('create.html')

### PARSING

def optional_re(re):
    return "(?:%s)?" % re


def parse_logfile(logfile):
    loglines = []
    script_re = re.compile(r"Script (done|started) on .*")
    prompt_re = re.compile(r"^\\\\x1b\]0;[A-Za-z0-9@\-_:~/]*(?:\\\\x07)?(?:\\\\x1b\[\?1034h)?([A-Za-z0-9@\-_:;~/\\\\[\] ]*[$#] )")
    prompt_re_2 = re.compile(r"^(\[[A-Za-z0-9@\-_:;~/\\\\[\] ]*[$#] )")
    prompt_datetime_re = re.compile(r"\[(\d{6}\-\d\d:\d\d:\d\d)\]")
    prompt_last_re = re.compile(r".*(\[[A-Za-z0-9@\-_:;~/ ]*\][$#] )")
    arrow_re = re.compile(r"^(> )")
    nil_backspace_re = re.compile(r"\\\\x07")
    backspace_re = re.compile(r".\\\\x08\\\\x1b\[K")
    tab_re = re.compile(r"\\\\t")
    single_quote_re = re.compile(r"\\'")
    double_quote_re = re.compile(r"\\\"")
    begin_line_re = re.compile(r"^b(?:'\\'|\"'|'\")")
    end_line_re = re.compile(r"\\\\n(?:\\''|'\"|\"')$")
    spacing_char_re = re.compile(r"\\\\x1b\[[0-9;]*m")
    with open(logfile.strip()) as logs:
        command = []
        response = []
        for line in logs:
            line = str(ascii(line).encode('utf-8')) # [3:-5]

            for feature_re in [begin_line_re, end_line_re]:
                line = feature_re.sub('', line, count=1)


            print("LINE: ***>%s<***" % line)
            prompt = arrow = None
            # print("re groups:")
            # print(prompt_re.match(line).groups(0))
            # print("end re groups:")
            try:
                print("re groups:")
                print(prompt_re.match(line).groups(0))
                print("end re groups:")
                prompt = prompt_re.match(line).groups(0)[0]
            except AttributeError:
                try:
                    prompt = prompt_re_2.match(line).groups(0)[0]
                except AttributeError:
                    pass
            try:
                arrow = arrow_re.match(line)[0]
            except TypeError:
                pass

            line = tab_re.sub(' ', line)
            line = spacing_char_re.sub(' ', line)
            line = single_quote_re.sub('\'', line)
            line = double_quote_re.sub('"', line)
            
            feature_res = [script_re, prompt_re, prompt_re_2, nil_backspace_re, backspace_re]
            if not response:
                feature_res.append(arrow_re)
            for feature_re in feature_res:
                scrubbed_line = feature_re.sub('', line, count=1)
                while scrubbed_line != line:
                    line = scrubbed_line
                    scrubbed_line = feature_re.sub('', line, count=1)

            if prompt:
                try:
                    if response or command[0]['input']:
                        loglines.append({'command': command, 'response': response})
                except IndexError:
                    pass
                response = []
                time = ''
                try:
                    time = prompt_datetime_re.match(prompt).groups(0)[0]
                except AttributeError:
                    pass
                try:
                    prompt = prompt_last_re.match(prompt).groups(0)[0]
                except AttributeError:
                    pass
                command = [{'time': time, 'prompt': prompt, 'arrow': '', 'input': line}]
            elif arrow and not response:
                command.append({'time': '', 'prompt': '', 'arrow': arrow, 'input': line})
            elif line:
                response.append(line)
        if len(response) > 1 or response[0]:
            loglines.append({'command': command, 'response': response})
    return loglines 


def parse_and_render_template(logfile):
    return render_template('parse_log.html', loglines=parse_logfile(logfile))

def parse_multiple_and_render_template(logfiles):
    print(logfiles)
    loglines = {}
    for logfile_index, logfile in enumerate(logfiles):
        logtime = None
        hostname = logfile.split('_')[1]
        print("hostname: %s" % hostname)
        print("logfile: %s" % logfile)
        for logline in parse_logfile(logfile):
            print(logline)
            logline["logfile_index"] = logfile_index
            time = logline['command'][0]['time']
            print('time: %s' % time)
            if time not in loglines.keys():
                loglines[time] = {}
            if not hostname in loglines[time].keys():
                loglines[time][hostname] = []
            loglines[time][hostname].append(logline)

    sorted_loglines = []
    for logtime in sorted(list(loglines.keys())):
        for hostname in sorted(list(loglines[logtime].keys())):
            sorted_loglines.extend(loglines[logtime][hostname])
    print('SORTED_loglines: %s' % loglines)

    return render_template('parse_log.html', loglines=sorted_loglines)


@app.route("/parse", methods=('GET', 'POST'))
def home():
    if request.method == 'POST':
        logfile = request.form['logfile']

        if not logfile:
            flash('logfile is required!')
        else:
            return parse_and_render_template(logfile)

    return render_template('parse_form.html')

@app.route("/open", methods=('GET', 'POST'))
def open_logdir():
    if request.method == 'POST':
        logdir = request.form['logdir']

        ttyrec_files = [f for f in os.listdir(logdir) if f.endswith('.ttyrec')]

        if not logdir:
            flash('Please provide a logs directory.')
        else:
            return render_template('select_files.html', logdir=logdir, ttyrec_files=ttyrec_files)

    return render_template('open_form.html')

@app.route("/parsemultiple", methods=['POST'])
def parsemultiple():
    print(request.form)
    print(request.form.keys())
    print([logfile for logfile, status in request.form.items() if status == 'on'])

    return parse_multiple_and_render_template(["%s%s" % (request.form['logdir'], logfile) for logfile, status in request.form.items() if status == 'on'])


def wiki_format(proclines):
    output = []
    for index, procline in proclines.items():
        if procline['linetype'] == 'noop':
            continue
        if procline['linetype'] == 'diagnostic':
            output.append("=== Diagnose ===")
        elif procline['linetype'] == 'mutating':
            output.append("=== Take Action ===")
        for commandline in procline['command']:
            output.append(" '''" + commandline["prompt"] + commandline["arrow"] + "'''" + commandline["input"])
        for responseline in procline['response']:
            output.append(" " + responseline)
        output.append(procline['comment'])
    return "\n".join(output)

@app.route("/publish", methods=['POST'])
def publish():
   proclines = {}
   for (input_name, input_val) in request.form.items():
       attr, index = input_name.split(':')
       if attr in ['command', 'response']:
           input_val = eval(input_val)
       if index not in proclines:
           proclines[index] = {}
       proclines[index][attr] = input_val
   print(proclines)
   return render_template('publish_log.html', formatted_proclines=wiki_format(proclines))

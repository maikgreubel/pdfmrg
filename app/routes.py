from flask import flash, redirect, render_template, send_file, request, session
from werkzeug.utils import secure_filename
from urllib.parse import parse_qs
import os
import glob
import uuid
import pymupdf
import tempfile
import logging

from app import app

log = logging.getLogger(__name__)
logging.basicConfig(format="%(levelname)s [%(asctime)s] %(message)s", level=logging.INFO)

ALLOWED_EXTENSIONS = {'pdf'}

def get_temp_dir() -> str:
    """Return the full qualified path of temporary directory"""
    return os.path.join(app.config['UPLOAD_FOLDER'], session['uid'].hex)

def allowed_ext(filename) -> bool:
    """Check whether given file name is in list of allowed extensions"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_idx_pdfname(idx) -> str:
    """Retrieve a pdf file name upon its index part"""
    for name in sorted(glob.glob(get_temp_dir() + "/" + str(idx) + "_*.pdf")):
        return os.path.basename(name)

    return None

def update_idx(idx:int):
    """Update indices in file names after a deletion"""
    tmpdir = get_temp_dir()

    for i in range(int(idx), int(session['fileid'])):
        name = get_idx_pdfname(i + 1)
        os.rename(
            os.path.join(tmpdir, name), 
            os.path.join(tmpdir, str(i) + "_" + name.split('_', 1)[1])
        )

def get_shots(tmpdir:str) -> list:
    """Retrieve a list of objects with fields 'image', 'idx' and 'original'"""
    shots=[]

    if not os.path.exists(tmpdir):
        return shots
    
    dir = os.fsencode(tmpdir)

    for file in os.listdir(dir):
        fname = file.decode(encoding='utf-8')

        if not allowed_ext(fname):
            continue

        idx = fname.split('_', 1)[0]
        origname = fname.split('_', 1)[1]
        shots.append({'image':fname, 'idx': idx, 'original': origname})

    return sorted(shots, key=lambda d: d['idx'])

def init_session():
    """Initialize the session - if necessary"""
    if not session.get('uid'):
        session['uid'] = uuid.uuid4()

@app.route('/')
@app.route('/index')
def index():
    """Either display the index or save the uploaded pdf"""
    init_session()

    try:
        return render_template('index.html', shots = get_shots(get_temp_dir()))
    except Exception as ex:
        log.error(ex)
    return redirect('/')

@app.route('/upload', methods=['GET','POST'])
def upload():
    """Perform the upload of file and redirect to index"""
    init_session()
    try:
        if request.method == 'POST':
            tmpdir = get_temp_dir()
            if 'file' not in request.files:
                flash('No file part')
                return redirect(request.url)
            
            file = request.files['file']

            if file.filename == '':
                flash('No file selected')
                return redirect(request.url)
            
            if file and allowed_ext(file.filename):
                if not session.get('fileid'):
                    session['fileid'] = 1

                fileid = session['fileid']
                session['fileid'] = fileid + 1
                filename = str(fileid) + "_" + secure_filename(file.filename)

                if not os.path.exists(tmpdir):
                    os.mkdir(tmpdir)

                path = os.path.join(tmpdir, filename)
                file.save(path)
                log.info("Uploaded " + path)
    except Exception as ex:
        log.error(ex)
    return redirect('/')

@app.route('/shots/<string:pdfname>')
def show_shot(pdfname):
    """Display the png for the given pdf"""
    init_session()
    try:
        pdfname = secure_filename(pdfname)
        tmpdir = get_temp_dir()
        image = os.path.join(tmpdir, pdfname + '.png')

        if not os.path.exists(image):
            pages = pymupdf.open(os.path.join(tmpdir, pdfname))

            for _, page in enumerate(pages):
                page.get_pixmap().save(image)
                break

        return send_file(image, mimetype='image/png')
    except Exception as ex:
        log.error(ex)
    
    return redirect('/')

@app.route('/delete/<string:pdfname>')
def remove_shot(pdfname):
    """Delete the pdf file and png identified by pdfname"""
    init_session()
    try:
        pdfname = secure_filename(pdfname)
        tmpdir = get_temp_dir()
        image = os.path.join(tmpdir, pdfname + '.png')
        pdf = os.path.join(tmpdir, pdfname)
        os.remove(pdf)
        if(os.path.exists(image)):
            os.remove(image)
        log.info("Removed " + pdf + " and its image")
        shots = get_shots(tmpdir)

        if len(shots) == 0:
            session['fileid'] = 1
        else:
            session['fileid'] = session['fileid'] - 1

        if len(shots) > 1:
            idx = pdfname.split('_')[0]
            update_idx(idx)
    except Exception as ex:
        log.error(ex)

    return redirect("/")

@app.route('/reorder/<string:neworder>')
def reorder(neworder):
    """Renames all pdf files according the new order"""
    init_session()
    try:
        order = parse_qs(neworder)['order[]']
        tmpdir = get_temp_dir()
        files = []
        for name in sorted(glob.glob(get_temp_dir() + "/*.pdf")):
            files.append(os.path.basename(name))

        log.info(order)
        log.info(files)

        newidx = 1

        for i in range(len(order)):
            idx = int(order[i])-1
            oldname = files[idx]
            newname = str(newidx)  + "_" + files[idx].split('_', 1)[1]

            log.info(oldname + " to be " + newname)

            if(oldname != newname):
                os.rename(
                    os.path.join(tmpdir, oldname), 
                    os.path.join(tmpdir, newname)
                )
                os.rename(
                    os.path.join(tmpdir, oldname + ".png"), 
                    os.path.join(tmpdir, newname + ".png")
                )
            newidx = newidx + 1
    except Exception as ex:
        log.error(ex)

    return redirect('/')

@app.route('/merge')
def merge_and_download():
    """Merges all pdf files according the index in temporary directory"""
    init_session()
    try:
        tmpdir = get_temp_dir()
        tmpname = next(tempfile._get_candidate_names())

        target = os.path.join(tmpdir, tmpname)
        
        pdf = pymupdf.open()
        for name in sorted(glob.glob(get_temp_dir() + "/*.pdf")):
            pdf.insert_file(os.path.join(tmpdir, name))
        pdf.save(target)
        pdf.close()

        return send_file(
            target, 
            as_attachment = True,
            mimetype = "application/pdf", 
            download_name = os.path.basename(target) + ".pdf"
        )
    except Exception as ex:
        log.error(ex)

    return redirect('/')

@app.route('/cleanup')
def cleanup_all():
    """Cleanup all resources by simply deleting pdf and its corresponding image"""
    init_session()
    try:
        tmpdir = get_temp_dir()
        for name in sorted(glob.glob(get_temp_dir() + "/*.pdf")):
            os.remove(os.path.join(tmpdir, name))
            if(os.path.exists(os.path.join(tmpdir, name+".png"))):
                os.remove(os.path.join(tmpdir, name+".png"))
        session['fileid'] = 1
    except Exception as ex:
        log.error(ex)

    return redirect('/')
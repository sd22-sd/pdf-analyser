import shutil

def create_zip(folder_path, zip_name):
    return shutil.make_archive(zip_name, 'zip', folder_path)

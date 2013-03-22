from django import template
from django.conf import settings

register = template.Library()

class PluploadScript(template.Node):
    def __init__(self,temp_ad_pk, csrf_token):
        self.temp_ad_pk = template.Variable(temp_ad_pk)
        self.csrf_token = template.Variable(csrf_token)
    def render(self, context):
        return """
            <script type="text/javascript" src="/static/js/plupload/plupload.full.js"></script>
            <script type="text/javascript" src="/static/js/plupload/jquery.plupload.queue/jquery.plupload.queue.js"></script>
            <script type="text/javascript">
                var uploader;
                $(document).ready(function() {
                //-----------------------------------------------------------------------------
                //  Plupload	setup and functions
                //-----------------------------------------------------------------------------
                // -------------Setup----------------
                uploader = new plupload.Uploader({
                    // General settings
                    runtimes : 'gears,html5,flash',
                    url : '/ads/plupload/',
                    max_file_size : '5mb',
                    container: 'uploader_cont',
                    browse_button : 'pickfiles',
                    unique_names : true,
                    multipart_params: {"csrfmiddlewaretoken" : "%s",
                        "temp_ad_pk" :  %s,
                        "type_pk": 1},
                    // Resize images on clientside if we can
                    resize : {width : 640, height : 480, quality : 90},
                    // Specify what files to browse for
                    filters : [
                        {title : "Image files", extensions : "jpg,png,jpeg"}
                    ],
                    // Flash settings
                    flash_swf_url : '%sjs/plupload/plupload.flash.swf'
                });

                // -------------Funcion que se ejecuta al inicializar Plupload----------------
                uploader.bind('Init', function(up, params) {
                    //$('#filelist').html("<div>Current runtime: " + params.runtime + "</div>");
                });

                $('#uploadfiles').click(function(e) { //se vincula el boton "uploadfiles" con la carga de imagenes
                    uploader.start();

                    $("#uploadfiles").hide();
                    $("#thumbs_cont").append("<div id='loader'><img src='%simages/loader.gif'/><span>Cargando im&aacute;genes...</span></div>");

                    e.preventDefault();
                });
                $('#uploadfiles_table').click(function(e) { //se vincula el boton "uploadfiles" de la tabla con la carga de imagenes
                    uploader.start();
                    $("#thumbs_cont").append("<div id='loader'><img src='%simages/loader.gif'/><span>Cargando im&aacute;genes...</span></div>");

                    e.preventDefault();
                });
                uploader.init();
                // -------------Se genera la tabla de archivos agregados----------------
                uploader.bind('FilesAdded', function(up, files) {
                    $('#filelist').removeClass("hidden");
                    $("#pickfiles").html("Seleccionar Archivos").removeClass("darkblue");
                    $("#upload_buttons").addClass("table");
                    $.each(files, function(i, file) {
                        var nombre_archivo, extencion;
                        if (file.name.length>14){
                            nombre_archivo=file.name.substr(0, 14)+"&tilde;"+file.name.substr(file.name.length-4, file.name.length)

                        }else{
                            nombre_archivo=file.name;
                        }
                        $('#filelist').append(
                                '<div id="' + file.id + '" class="file_row"><span class="archivo">' +
                                        nombre_archivo + '</span><span class="tamanio">' + plupload.formatSize(file.size) + '</span>'+
                                        '<span class="progreso"><span></span>'+
                                        '<div id="progress-bar">'+
                                        '<div id="progress-level"></div>'+
                                        '</div>'+
                                        '</span>' +
                                        '</div>');
                        $("#thumbs_cont").append('<div id="thumb_' + file.id + '" class="thumb_container hidden"></div>');
                    });

                    if($("#thumbs_cont").is(":hidden")){
                        $("#thumbs_cont").removeClass("hidden");
                    }
                    if($("#thumbs_cont").height()<$("#filelist").height()){

                        $("#thumbs_cont").css("min-height", $("#filelist").height()+38);
                    }

                    if($("#thumbs_cont div").not(".hidden").length==0){ //Muestra el boton grande solo cuando no hay imagenes guardadas

                        $("#uploadfiles").show();
                    }//else{
                    $("#uploadfiles_table").show();
                    //}

                    up.refresh(); // Reposition Flash/Silverlight
                });
                // -------------Funcion que se ejecuta al actualizarse el progreso de subida de un archivo
                uploader.bind('UploadProgress', function(up, file) {
                    $('#' + file.id + " .progreso span").html(file.percent + "%%");
                    $("#progress-level").css("width",file.percent + "%%");
                });
                // -------------Detecta errores y elimina archivos conflictivos----------------
                uploader.bind('Error', function(up, err) {
                    $('#uploader_cont').append("<div id='err_"+err.file.id+"'>Error: " + err.code +
                            ", Message: " + err.message +
                            (err.file ? ", File: " + err.file.name : "") +
                            "</div>"
                    );
                    $("#err_"+err.file.id).remove();
                    setTimeout("remove_rows('"+err.file.id+"')",1000);
                    uploader.removeFile(err.file);
                    up.refresh(); // Reposition Flash/Silverlight
                });
                // -------------Trae imagenes subidas----------------
                uploader.bind('FileUploaded', function(up, file) {
                    var url="/ads/temp_images/%s/?query=1";

                    $("#thumb_"+file.id).load(url, function(){
                        $("#thumb_"+file.id).prepend('<span class="file_name">'+file.name+'</span>');
                    }).removeClass('hidden');

                    $(".desc").removeClass("hidden");

                    $("#"+file.id).remove();

                    $("#thumbs_cont #loader").remove();
                    $("#pickfiles").show();

                    $("#uploadfiles").hide();
                    $("#uploadfiles_table").show();

                });
                });
                function remove_rows(id){
                    $("div#"+id).remove();
                }
                //-----------------------------------------------------------------------------
                //  elemino la imagen seleccionada de todos lados(form, server, db)
                //-----------------------------------------------------------------------------
                function delete_pic(imagen){
                    var nom_img=$(imagen).find(".uploaded_img").attr("src");
                    nom_img=nom_img.split("/");
                    nom_img=nom_img[nom_img.length-1];
                    var url="/ads/del_temp_images/%s/?query="+nom_img;
                    $(imagen).load(url,function(){
                        $(imagen).remove();
                    });
                }
            </script>

            """ % (self.csrf_token.resolve(context), self.temp_ad_pk.resolve(context),settings.STATIC_URL,settings.STATIC_URL,settings.STATIC_URL,self.temp_ad_pk.resolve(context),self.temp_ad_pk.resolve(context))


def plupload_script(parser, token):
    tag_name, temp_ad_pk, csrf_token_form = token.split_contents()

    return PluploadScript(temp_ad_pk, csrf_token_form)

register.tag("plupload_script", plupload_script)

class PluploadForm(template.Node):
    def render(self, context):
        return """
                    <div id="uploader_cont">
                        <div id="table_cont">
                            <div id="file_list_buttons">
                                <div id="filelist" class="hidden">
                                    <div id="table_header">
                                        <span id="head_archivo">Archivo</span>
                                        <span id="head_size">Tama&ntilde;o</span>
                                        <span id="head_progress">Proceso</span>
                                    </div>

                                </div>
                                <div id="upload_buttons">
                                    <button id="uploadfiles_table" href="#" class="default_button_upload hidden darkblue">Cargar</button>
                                    <button id="pickfiles" href="#" class="default_button_upload darkblue">Seleccionar Im&aacute;genes</button>
                                </div>
                            </div>

                        </div>

                        <div id="thumbs_cont"  class="thumbs hidden">
                            <span class="desc hidden">Escoje la portada de tu anuncio</span>
                        </div>

                    </div>
        """

def pl_upload_form(parser, token):

    return PluploadForm()

register.tag("pl_upload_form", pl_upload_form)
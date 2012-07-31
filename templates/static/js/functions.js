function addCommas(nStr){
    /*
    * Convierte una cadena a un formato numerico separado por comas
    * addCommas("1450332")
    * return 1,450,332
    * */
    nStr += '';
    x = nStr.split('.');
    x1 = x[0];
    x2 = x.length > 1 ? '.' + x[1] : '';
    var rgx = /(\d+)(\d{3})/;
    while (rgx.test(x1)) {
        x1 = x1.replace(rgx, '$1' + ',' + '$2');
    }
    return x1 + x2;
}


function isValidEmailAddress(emailAddress) {
    /*
    * Prueba si una cadena dada es una dirección valida de correo electronico
    * isValidEmailAddress("hector@wime.com");
    * return true
    *
    * isValidEmailAddress("algo");
    * return false;
    * */
    var pattern = new RegExp(/^(("[\w-\s]+")|([\w-]+(?:\.[\w-]+)*)|("[\w-\s]+")([\w-]+(?:\.[\w-]+)*))(@((?:[\w-]+\.)*\w[\w-]{0,66})\.([a-z]{2,6}(?:\.[a-z]{2})?)$)|(@\[?((25[0-5]\.|2[0-4][0-9]\.|1[0-9]{2}\.|[0-9]{1,2}\.))((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[0-9]{1,2})\.){2}(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[0-9]{1,2})\]?$)/i);
    return pattern.test(emailAddress);
}

function getUrlVars()
{
    /*
     * Obtiene las variables get de la página actual y regresa un arreglo asociativo
     * URI= /?var1=1&var2=2
     * get=getUrlVars();
     *
     * get['var1']=1
     * get['var2']=2
     * */
    var vars = [], hash;
    var hashes = window.location.href.slice(window.location.href.indexOf('?') + 1).split('&');

    for(var i = 0; i < hashes.length; i++)
    {
        hash = hashes[i].split('=');
        vars.push(hash[0]);
        vars[hash[0]] = hash[1];
    }

    return vars;
}
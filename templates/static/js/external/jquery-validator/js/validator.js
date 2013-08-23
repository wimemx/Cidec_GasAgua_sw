(function($){
 $.fn.validate = function(c_options) {
   var defaults = {
      class_: ".validate",
      maxlength: 300,
      correct_img: "/static/css/images/imgs_icns/correct.png",
      incorrect_img: "/static/css/images/imgs_icns/incorrect.png",
      onsubmit: null
   };
   var options = $.extend(defaults, c_options);
   var back_correct = "url("+options.correct_img+") no-repeat";
   var back_incorrect = "url("+options.incorrect_img+") no-repeat";
   var send = 0;
   var valid_form = true;
   
   var validate_input = function (element, element_value) {
       var regexp, back_;
       if (element.hasClass("alphanumeric")) {
           regexp = new RegExp(/^[A-Za-z0-9ÁÉÍÓÚáéíóuñÑ '\.,"]+$/);
       } else if (element.hasClass("numeric")) {
           regexp = new RegExp(/^\d{1,3}(,?\d{3})*?(.\d*)?$/g);
       } else if (element.hasClass("alpha")) {
           regexp = new RegExp(/^[A-Za-zÁÉÍÓÚáéíóuñÑ '\.,"]+$/);
       } else if (element.hasClass("email")) {
           regexp = new RegExp(/^(("[\w-\s]+")|([\w-]+(?:\.[\w-]+)*)|("[\w-\s]+")([\w-]+(?:\.[\w-]+)*))(@((?:[\w-]+\.)*\w[\w-]{0,66})\.([a-z]{2,6}(?:\.[a-z]{2})?)$)|(@\[?(25[0-5]\.|2[0-4][0-9]\.|1[0-9]{2}\.|[0-9]{1,2}\.)((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[0-9]{1,2})\.){2}(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[0-9]{1,2})\]?$)/i);
       }
       else if (element.hasClass("url")) {
           regexp = new RegExp(/^(ht|f)tps?:\/\/[a-z0-9-\.]+\.[a-z0-9]{2,4}\/?([^\s<>#%",\{\}\\|\\\^\[\]`]+)?$/);
       }
       if(element.hasClass("notnull")){
           if ($.trim(element_value) == '') {
               back_ = back_incorrect;
               valid_form = false;
           }else{
               if(regexp != undefined){
                   if (regexp.test(element_value)) {
                       back_ = back_correct;
                   } else {
                       back_ = back_incorrect;
                       valid_form = false;
                   }
               }

           }
       }else{
           if ($.trim(element_value) != '') {
               if (regexp.test(element_value)) {
                   back_ = back_correct;
               } else {
                   back_ = back_incorrect;
                   valid_form = false;
               }
           }
       }
       element.next().css("background", back_);
       return valid_form;
   };
   var validate_option = function(element, element_value){
       var back_;
       if(element_value=='0' || element_value==''){
           back_ = back_incorrect;
           valid_form = false;
       }else{
           back_ = back_correct;
       }
       if(element.parent().hasClass("selector") || element.parent().hasClass("uniform") ){
           element.parent().next().css("background", back_);
       }else{
           element.next().css("background", back_);
       }

       return valid_form;
   };

   return this.each(function() {
      var obj = $(this);//form
      obj.find(options.class_).each(function(){
         var obj_=$(this);
         if(obj_.parent().hasClass("selector") || obj_.parent().hasClass("uniform") ){
             obj_.parent().after("<span class='status'></span>");
         }else{
             obj_.after("<span class='status'></span>");
         }

         obj_.keyup(function(){
            if(obj_.val().length > options.maxlength){
               obj_.val(obj.val().substring(0, options.maxlength));
            }
         });
         obj_.blur(function(e){
            var element = $("#"+e.delegateTarget.id);
            var element_value = $.trim(element.val());
            var element_type = e.delegateTarget.nodeName.toLowerCase();
            if(element_type == "input" || element_type == "textarea"){
               validate_input(element, element_value);
            }else{
                //validate option
                validate_option(element, element_value);
            }
         });
      });
      obj.submit(function() {
         var valid_f = function(){
            valid_form = true;
            obj.find(options.class_).each(function(){
                var element = $(this);
                var element_value = $.trim(element.val());
                var element_type = element[0].tagName.toLowerCase();
                if(element_type == "input" || element_type == "textarea"){
                    valid_form = validate_input(element, element_value);
                }else{
                    //validate option
                    valid_form = validate_option(element, element_value);
                }
            });
            return valid_form;
         };
         if(valid_f()){
            send++;
         }

         if(send === 1 && options.onsubmit){
             return options.onsubmit(obj.serialize());
         }else{
             return send === 1;
         }
      });
   });
 };
})(jQuery);

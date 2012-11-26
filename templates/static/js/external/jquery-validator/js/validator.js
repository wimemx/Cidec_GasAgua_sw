(function($){
 $.fn.validate = function() {
   var defaults = {
      class_: ".validate",
      maxlength: 300,
      //allow: "alphanumeric", //numeric, alpha, email, url, notnull
      correct_img: "imgs/correct.png",
      incorrect_img: "imgs/incorrect.png"
   };
   var options = $.extend(defaults, options);
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
           regexp = new RegExp(/^(ht|f)tps?:\/\/[a-z0-9-\.]+\.[a-z]{2,4}\/?([^\s<>#%",\{\}\\|\\\^\[\]`]+)?$/);
       }
       if ($.trim(element_value) != '') {
           if (regexp.test(element_value)) {
               back_ = back_correct;
           } else {
               back_ = back_incorrect;
               valid_form = false;
           }
       } else {
           back_ = back_incorrect;
           valid_form = false;
       }
       element.next().css("background", back_);
   };

   return this.each(function() {
      var obj = $(this);//form
      var valid_form = true;
      obj.find(options.class_).each(function(){
         var obj_=$(this);
         obj_.after("<span class='status'></span>");
         obj_.keyup(function(){
            if(obj_.val().length > options.maxlength){
               obj_.val(obj.val().substring(0, options.maxlength));
            }
         });
         obj_.blur(function(e){
            var element = $("#"+e.delegateTarget.id);
            var element_value = $.trim(element.val());
            var element_type = e.delegateTarget.nodeName.toLowerCase();
            var back_;
            if(element_type == "input"){
               validate_input(element, element_value);
            }else{
               //validar option
            }
            
            
         });
      });
      obj.submit(function() {
         valid_form = function(){
            
            };
         if(valid_form){
            send++;
         }
         if(send == 1){
            return valid_form;
         }else{
            return false;
         }
         
      });
   });
 };
})(jQuery);

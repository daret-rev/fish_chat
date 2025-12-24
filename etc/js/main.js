
(function ($) {
    "use strict";


     /*==================================================================
    [ Focus input ]*/
    $('.input100').each(function(){
        $(this).on('blur', function(){
            if($(this).val().trim() != "") {
                $(this).addClass('has-val');
            }
            else {
                $(this).removeClass('has-val');
            }
        })    
    })
  
  
    /*==================================================================
    [ Validate ]*/
    var input = $('.validate-input .input100');

    $('.validate-form').on('submit',function(){
       

        var check = true;
        var form = $(this);

        for(var i=0; i<input.length; i++) {
            if(validate(input[i]) == false){
                showValidate(input[i]);
                check=false;
            }
        }

        if(check) {
            var username = $('input[name="username"]').val();
            var password = $('input[name="password"]').val();

            var formData = {
                username: username,
                password: password

            };

            if(!username || !password) {
                showLoginError('Заполните все поля')
                return false
            }
            
            console.log('DEBUG start')
            console.log('Полученные данные:', formData)

            $('.login100-form-btn').prop('disabled', true).text('Вход...');

            $.ajax({
                url: form.attr('action'),
                type: 'POST',
                data: formData,
                success: function(response) {
                    if(response.success) {
                        window.location.href = response.redirect;
                    } else {
                        showLoginError(response.message || 'Ошибка входа');
                        $('.login100-form-btn').prop('disable', false).text('Вход');
                    }
                },
                error: function(xhr) {
                    showLoginError('Ошибка сервера. Попробуйте позже.');
                $('.login100-form-btn').prop('disable', false).text('Вход');
                }
                
            });
        }

        return false;
    });

    function showLoginError(message) {
        var errorDiv = $('.login-error')

        if(!errorDiv.length) {
            errorDiv = $('<div class="login-error" style="color: red; margin-top: 10px;"></div>');
            $('.validate-form').append(errorDiv)
        }
        errorDiv.text(message).show();

        setTimeout(function() {
            errorDiv.fadeOut();
        }, 5000)
    }

    $('.validate-form .input100').each(function(){
        $(this).focus(function(){
           hideValidate(this);
        });
    });

    function validate (input) {
        if($(input).attr('type') == 'email' || $(input).attr('name') == 'email') {
            if($(input).val().trim().match(/^([a-zA-Z0-9_\-\.]+)@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.)|(([a-zA-Z0-9\-]+\.)+))([a-zA-Z]{1,5}|[0-9]{1,3})(\]?)$/) == null) {
                return false;
            }
        }
        else {
            if($(input).val().trim() == ''){
                return false;
            }
        }
    }

    function showValidate(input) {
        var thisAlert = $(input).parent();

        $(thisAlert).addClass('alert-validate');
    }

    function hideValidate(input) {
        var thisAlert = $(input).parent();

        $(thisAlert).removeClass('alert-validate');
    }
    
    

})(jQuery);
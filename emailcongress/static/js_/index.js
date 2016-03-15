(function(){
    $(document).ready(function(){

        var $email_form = $('#email-form');
        var $email_form_wrapper = $('.email-form-wrapper');
        var $email_form_submit = $email_form.find('button[type="submit"]').first();
        var $update_address_h3 = $('[data-js=update_address-h3]');
        var $remind_reps_h3 = $('[data-js=remind_reps-h3]');
        var $toggle_email_form = $('[data-js=toggle-email-form]');
        var $email_form_message = $('[data-js=email-form-message]');

        $toggle_email_form.click(function() {
            $email_form_message.hide();
            $toggle_email_form.removeClass('is-active');
            $(this).addClass('is-active');

            var id = $(this).attr('id');
            $email_form_submit.attr('value', id);
            $email_form_wrapper.show();

            $email_form.children('h3').hide();
            if (id == 'update_address') {
                $update_address_h3.show();
            } else if (id == 'remind_reps') {
                $remind_reps_h3.show();
            }
        });

        $email_form.submit(function(event) {
            event.preventDefault();
            $.ajax({
                type: 'POST',
                url: URL_PREFIX + '/',
                data: $(this).serialize()+'&submit_type='+$email_form_submit.attr('value'),
                dataType: 'json',
                timeout: 3000,
                success: function (result) {
                    $email_form_message.text(result['email']);
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    console.log(textStatus);
                    console.log(errorThrown);
                    console.log(jqXHR);
                    $email_form_message.text(jqXHR['responseJSON']['email']);
                },
                complete: function (jqXHR, textStatus) {
                    $email_form_message.show();
                }
            });
        })
    });
})();
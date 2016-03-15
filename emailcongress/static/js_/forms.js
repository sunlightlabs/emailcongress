(function(){
    $(document).ready(function () {
        try {
            $(".button__primary[type='submit']").click(function(event) {
                var checked = false;
                $('.repcard__checkbox').each(function(index, value) {
                    if ($(value).prop('checked')) {
                        checked = true;
                    }
                });
                if (!checked) {
                    event.preventDefault();
                }
            });

            // Remove gray placeholder appearance from select
            $('.form__select').on('change', function () {
                $(this).removeClass('is-gray');
            });

            function checkSubmitButton()
            {
                var checked = false;
                $('.repcard__checkbox').each(function(index, value) {
                    if ($(value).prop('checked')) {
                        checked = true;
                    }
                });
                if (!checked) {
                    $(".button__primary[type='submit']").addClass('is-disabled');
                }
                else {
                    $(".button__primary[type='submit']").removeClass('is-disabled');
                }
            }

            checkSubmitButton();

            // Toggle checkbox when repcard is clicked
            $('.repcard').on('click', function (e) {
                if (!$(this).hasClass('repcard--horizontal')) {
                    $(this).toggleClass('is-selected');
                    $(this).find('.repcard__checkbox').each(function() {
                        var checkbox = $(this);
                        checkbox.prop("checked", !checkbox.prop("checked"));
                    });
                    checkSubmitButton();
                }
                else {
                    window.location.href = $(this).find('a').first().attr('href');
                }
            });

            // Toggle repcard when checkbox is clicked
            $('.repcard__checkbox').click(function (e) {
                e.stopPropagation();
                $(this).parents('.repcard').toggleClass('is-selected');
                checkSubmitButton();
            });
        } catch(errors) {}
    });
})();

/* Brazilan initialisation for the timepicker plugin */
/* Written by staniel Almeida (quantostaniel@gmail.com). */
jQuery(function($){
    $.timepicker.regional['pt-BR'] = {
                hourText: 'Hora',
                minuteText: 'Minuto',
                amPmText: ['AM', 'PM'],
                closeButtonText: 'Fechar',
                nowButtonText: 'Agora',
                deselectButtonText: 'Limpar' }
    $.timepicker.setDefaults($.timepicker.regional['pt-BR']);
});
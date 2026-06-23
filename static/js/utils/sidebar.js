/**
 * Utilidades de sidebar responsive
 * Manejo del sidebar en dispositivos móviles
 */

$(document).ready(function() {
  // Crear overlay para sidebar en móvil
  if ($('.sidebar-overlay').length === 0) {
    $('body').append('<div class="sidebar-overlay"></div>');
  }
  
  // Forzar cierre del sidebar al cargar la página
  $('body').removeClass('sidebar-open');
  $('.sidebar-overlay').removeClass('show');
  
  // Manejar click en el botón de toggle del sidebar
  $('#sidebar-toggle').on('click', function(e) {
    e.preventDefault();
    
    if ($(window).width() <= 768) {
      // En móvil: usar nuestro sistema personalizado
      $('body').toggleClass('sidebar-open');
      $('.sidebar-overlay').toggleClass('show');
    } else {
      // En desktop: usar el comportamiento normal de AdminLTE
      $('body').toggleClass('sidebar-collapse');
    }
  });
  
  // Manejar click en el overlay para cerrar sidebar
  $(document).on('click', '.sidebar-overlay', function() {
    $('body').removeClass('sidebar-open');
    $('.sidebar-overlay').removeClass('show');
  });
  
  // Cerrar sidebar al cambiar el tamaño de la ventana a desktop
  $(window).on('resize', function() {
    if ($(window).width() > 768) {
      $('body').removeClass('sidebar-open');
      $('.sidebar-overlay').removeClass('show');
    }
  });
  
  // Cerrar sidebar al navegar a otra página
  $(document).on('click', '.nav-sidebar .nav-link', function() {
    if ($(window).width() <= 768) {
      $('body').removeClass('sidebar-open');
      $('.sidebar-overlay').removeClass('show');
    }
  });
});

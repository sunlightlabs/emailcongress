// update package.json to latest with "npm-check-updates -u"

var gulp      = require('gulp'),
    sass      = require('gulp-sass'),
    concat    = require('gulp-concat'),
    minifyCSS = require('gulp-minify-css'),
    rename    = require('gulp-rename'),
    uglify    = require('gulp-uglify');
    fs        = require('fs');

var project = 'emailcongress';

gulp.task('sass', function () {
  return gulp.src('./' + project + '/static/sass/*.scss')
             .pipe(sass().on('error', sass.logError))
             .pipe(concat('./' + project + '/static/css/emailcongress.css'))
             .pipe(minifyCSS())
             .pipe(rename(project + '.min.css'))
             .pipe(gulp.dest('./' + project + '/static/css/'));
});

gulp.task('scripts', function() {
  return gulp.src('./' + project + '/static/js_/*.js')
             .pipe(concat('./' + project+ '/static/js/emailcongress.js'))
             .pipe(uglify())
             .pipe(rename(project + '.min.js'))
             .pipe(gulp.dest('./' + project + '/static/js/'))
});

function watch() {
  gulp.watch('./' + project + '/static/js_/*.js', ['scripts']);
  gulp.watch('./' + project + '/static/sass/**', ['sass']);
}

gulp.task('default', watch);
gulp.task('watch', watch);
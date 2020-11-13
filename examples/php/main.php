<?php
phpinfo();

function step_over_me() {
    echo 'stepping over me';
}

function step_into_me() {
    step_over_me();
}

for ($i=0; $i < 100; $i++) {
    step_into_me();
}

?>
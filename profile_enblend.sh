#!/usr/bin/env bash
./profile_enblend.py --title "enblend 4.2 2720x1824 ymf292-f, inc" --save profile_enblend/yamaha_ymf292-f_mz_mit20x2_inc.png /mnt/m10_4/buffer/ic/yamaha/yamaha_ymf292-f_mz_mit20x2/raw.3_stx1_fine_mask/pr0nts/main.log,fine /mnt/m10_4/buffer/ic/yamaha/yamaha_ymf292-f_mz_mit20x2/raw.4_stx1_course_mask/pr0nts/w00.log,course
./profile_enblend.py --net --title "enblend 4.2, 2720x1824, ymf292-f, net" --save profile_enblend/yamaha_ymf292-f_mz_mit20x2_net.png /mnt/m10_4/buffer/ic/yamaha/yamaha_ymf292-f_mz_mit20x2/raw.3_stx1_fine_mask/pr0nts/main.log,fine /mnt/m10_4/buffer/ic/yamaha/yamaha_ymf292-f_mz_mit20x2/raw.4_stx1_course_mask/pr0nts/w00.log,course
./profile_enblend.py --net --title "enblend ver?, 2720x1824, 50299a, net" --save profile_enblend/pricer_50299a_delayer_mit20x2_net.png /mnt/m10_4/buffer/ic/dmitry/pricer_50299a_delayer_mit20x2/raw/pr0nts/w00.log
./profile_enblend.py --net --title "enblend ver?, 1632x1224, vsop, net" --save profile_enblend/sharp_vsop_mz_mit20x_net.png /mnt/m10_4/buffer/ic/sharp_vsop_mz_mit20x/pr0nts/w00.log

./profile_enblend.py --net --title "1632x1224, ix0908ce, net" --save profile_enblend/sharp_ix0908ce-cynthia-jr_mz_mit20x_net.png \
    /mnt/m10_4/buffer/ic/sharp_ix0908ce-cynthia-jr_mz_mit20x/raw/pr0nts/w00.log,"enblend 4.1 cached" \
    /mnt/m10_4/buffer/ic/sharp_ix0908ce-cynthia-jr_mz_mit20x/raw.2_enblend_fine/pr0nts/w00.log,"enblend 4.2 fine" \
    /mnt/m10_4/buffer/ic/sharp_ix0908ce-cynthia-jr_mz_mit20x/raw.3_enblend_course/pr0nts/w00.log,"enblend 4.2 course"



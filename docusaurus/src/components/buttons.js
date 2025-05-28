import {styled} from "@mui/material/styles";
import {Button} from "@mui/material";

export const LowercaseButton = styled(Button)(
    ({}) => ({
        textTransform: 'none !important',
        fontSize: 12
    })
)
